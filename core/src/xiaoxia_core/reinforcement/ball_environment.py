"""SO-101 小球抓取物理环境：独立状态、接触奖励和持续夹持抬升判定。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from copy import copy
from xml.etree import ElementTree as ET

import mujoco
import numpy as np

from ..contracts import Action
from ..safety import JOINTS, JointLimits
from ..simulation.world import MujocoSimulation, SimulationConfig
from .pickup_reward import PickupReward
from .pickup_phases import PickupPhases
from .pickup_curriculum import PickupCurriculum


class BallPickupEnvironment(MujocoSimulation):
    version = 'so101_pickup_v5_phase_sac'
    radius = 0.015
    episode_steps = 180
    floor_z = -.003
    lift_height = .05
    hold_seconds = 1.0

    def prepare_urdf(self, root, path):
        from .gripper_collision import GripperCollisionGeometry
        GripperCollisionGeometry().apply(root, path)

    def extend_scene(self, mjcf):
        world = mjcf.find('worldbody')
        ET.SubElement(world, 'geom', name='pickup_floor', type='plane', size='1 1 .05',
                      pos='0 0 -.003', friction='1 .01 .001', rgba='.8 .85 .82 1')
        ET.SubElement(world, 'light', name='pickup_fill', pos='0 0 1', dir='0 0 -1',
                      directional='true', ambient='.35 .35 .35', diffuse='.7 .7 .7')
        ball = ET.SubElement(world, 'body', name='pickup_ball', pos='.2 0 .015')
        ET.SubElement(ball, 'freejoint', name='pickup_ball_free')
        ET.SubElement(ball, 'geom', name='pickup_ball_geom', type='sphere', size=str(self.radius),
                      mass='.012', friction='1.5 .02 .002', condim='4', priority='1', solref='.008 1', rgba='1 .35 .15 1')
        gripper = mjcf.find(".//body[@name='gripper_link']")
        if gripper is None:
            raise ValueError('URDF 缺少 gripper_link，无法定位抓取点')
        ET.SubElement(gripper, 'site', name='pickup_tip', pos='.0071 -.000218121 -.092', size='.003')
        ET.SubElement(gripper, 'camera', name='pickup_wrist', pos='.0025 -.068697378 -.003110223',
                      quat='.976296007 .216439614 0 0', fovy='60')
        # 原生位置执行器在每个物理步计算 P 项，避免各环境在 Python 中逐轴逐步争用 GIL。
        actuators = mjcf.find('actuator')
        if actuators is None:
            actuators = ET.SubElement(mjcf, 'actuator')
        limits = JointLimits.from_urdf(self.config.urdf_path)
        for name in JOINTS:
            effort = min(self.config.max_torque, limits.joints[name].effort)
            ET.SubElement(actuators, 'position', name=f'pickup_{name}', joint=name,
                kp=str(self.config.position_gain), forcelimited='true', forcerange=f'{-effort} {effort}')

    @classmethod
    def vector(cls, urdf, count, seed):
        prototype = cls(SimulationConfig(urdf, max_velocity=1.0, max_torque=2.0))
        prototype.connect()
        environments = []
        for index in range(count):
            env = prototype if index == 0 else copy(prototype)
            env._data = mujoco.MjData(prototype._model)
            env.random = np.random.default_rng(seed + index)
            env.ball_joint = mujoco.mj_name2id(env._model, mujoco.mjtObj.mjOBJ_JOINT, 'pickup_ball_free')
            env.ball_geom = mujoco.mj_name2id(env._model, mujoco.mjtObj.mjOBJ_GEOM, 'pickup_ball_geom')
            env.tip = mujoco.mj_name2id(env._model, mujoco.mjtObj.mjOBJ_SITE, 'pickup_tip')
            env.jaws = {mujoco.mj_name2id(env._model, mujoco.mjtObj.mjOBJ_BODY, name)
                        for name in ('gripper_link', 'moving_jaw_so101_v1_link')}
            env.floor_geom = mujoco.mj_name2id(env._model, mujoco.mjtObj.mjOBJ_GEOM, 'pickup_floor')
            env.episode_index = 0
            env.reset_episode()
            environments.append(env)
        return environments

    def reset_episode(self, position=None):
        super().reset()
        model, data = self._state()
        address = model.jnt_qposadr[self.ball_joint]
        width = PickupCurriculum.widths[getattr(self, 'curriculum_level', 2)]
        xy = position if position is not None else [self.random.uniform(.195 - .035 * width, .195 + .035 * width), self.random.uniform(-.05 * width, .05 * width)]
        if len(xy) != 2 or not np.isfinite(xy).all() or not .16 <= xy[0] <= .23 or not -.05 <= xy[1] <= .05:
            raise ValueError('球位置超出已定义工作区')
        data.qpos[address:address + 3] = [*xy, self.floor_z + self.radius + .002]
        data.qpos[address + 3:address + 7] = [1, 0, 0, 0]
        mujoco.mj_forward(model, data)
        self.phases = PickupPhases()
        self.steps = self.held = 0
        self.held_seconds = 0.0
        self.ended = False
        self.episode_index += 1
        self.return_ = 0.0
        self._physics_step(track_hold=False)
        self.initial_ball_position = self.ball_position()
        self.spawn_position = self.initial_ball_position.copy()
        self.reward = PickupReward(float(np.linalg.norm(self.ball_position() - data.site_xpos[self.tip])))
        self.last_reward_terms = {}
        self.visual_reward_step = 0
        self.last_visual_reward = 0.0
        self.ball_visible = False
        return self.state()

    def ball_position(self):
        return self._data.geom_xpos[self.ball_geom].copy()

    def state(self):
        model, data = self._state()
        q = [data.qpos[model.jnt_qposadr[self._joints[name]]] for name in JOINTS]
        velocity = [data.qvel[model.jnt_dofadr[self._joints[name]]] for name in JOINTS]
        ball = self.ball_position()
        contact = self.contact_state()
        forces = [contact['jaw_forces'][name] for name in ('gripper_link', 'moving_jaw_so101_v1_link')]
        orientation = data.site_xmat[self.tip].reshape(3, 3)[:, 2] - [0, 0, 1]
        return np.asarray([*q, *velocity, *ball, *(ball - data.site_xpos[self.tip]),
            *self.phases.one_hot(), *[min(force, 2.) / 2 for force in forces],
            min(self.held_seconds / self.hold_seconds, 1.), *orientation], dtype=np.float32)

    def advance(self, action):
        if self.ended:
            raise ValueError('当前回合已结束，请先 reset_episode；不重复计算成功奖励')
        action = np.asarray(action)
        if action.shape != (6,) or action.dtype.kind not in 'fiu' or not np.isfinite(action).all() or np.max(np.abs(action)) > 1:
            raise ValueError('动作必须为六维 [-1,1] 有限数值')
        requested_action = action.copy()
        action = self.phases.mask(action)
        current = self.read_observation().joint_positions
        targets = {name: float(np.clip(current[name] + float(action[index]) * .08,
                   self.limits.joints[name].lower, self.limits.joints[name].upper)) for index, name in enumerate(JOINTS)}
        self.send_action(Action(targets))
        self._physics_step()
        model, data = self._state()
        contact = self.contact_state()
        ball = self.ball_position()
        distance = float(np.linalg.norm(ball - data.site_xpos[self.tip]))
        lifted = float(np.clip((ball[2] - self.initial_ball_position[2]) / self.lift_height, 0, 1))
        grasped = contact['both_jaws'] and not contact['ball_on_floor']
        success = self.held_seconds >= self.hold_seconds - 1e-8
        self.steps += 1
        failed = ball[2] < self.floor_z - .02 or float(np.linalg.norm(ball[:2])) > .6
        terminated = success or failed
        truncated = self.steps >= self.episode_steps and not terminated
        reward, self.last_reward_terms = self.reward.calculate(distance=distance, lift_fraction=lifted,
            grasped=grasped, success=success, failed=failed, truncated=truncated,
            action=action, floor_force=contact['arm_floor_force'],
            ball_contact=any(force > .01 for force in contact['jaw_forces'].values()))
        progress = self.phases.update(visible=self.ball_visible, delta=ball - data.site_xpos[self.tip],
            orientation_error=float(np.linalg.norm(data.site_xmat[self.tip].reshape(3, 3)[:, 2] - [0, 0, 1])),
            contact=contact, lifted=ball[2] - self.initial_ball_position[2],
            gripper=self.read_observation().joint_positions['gripper'])
        self.last_reward_terms['phase_progress'] = progress
        blocked = max(0., float(action[5] - requested_action[5]))
        self.last_reward_terms['premature_close'] = -.1 * blocked
        reward += progress - .1 * blocked
        self.return_ += reward
        self.ended = bool(terminated or truncated)
        return self.state(), reward, bool(terminated), bool(truncated), bool(success)

    def observe_ball_image(self, rgb):
        # 在主渲染线程读取干净 RGB；不把观测噪声当作奖励依据。
        red = rgb[:, :, 0].astype(np.float32)
        mask = (red > 40) & (red > rgb[:, :, 1] * 1.4) & (red > rgb[:, :, 2] * 1.4)
        self.ball_visible = bool(np.count_nonzero(mask) >= 6)
        if self.steps > self.visual_reward_step:
            self.last_visual_reward = self.reward.observe_ball(self.ball_visible)
            self.last_reward_terms['found_ball'] = self.last_visual_reward
            self.return_ += self.last_visual_reward
            self.visual_reward_step = self.steps

    def _physics_step(self, *, track_hold=True):
        model, data = self._state()
        for _ in range(10):
            data.qfrc_applied[:] = 0
            for index, name in enumerate(JOINTS):
                limit = self.limits.joints[name]
                increment = min(self.config.max_velocity, limit.velocity) * self.config.timestep * 10
                previous = self._setpoints[name]
                self._setpoints[name] = previous + min(max(self._targets[name] - previous, -increment), increment)
                dof = model.jnt_dofadr[self._joints[name]]
                # P 项由原生执行器逐步计算；10 个物理步更新一次重力/偏置补偿和速度受限设定点。
                data.ctrl[index] = self._setpoints[name] + data.qfrc_bias[dof] / self.config.position_gain
            mujoco.mj_step(model, data, nstep=10)
            if track_hold:
                contact = self.contact_state()
                valid = contact['both_jaws'] and not contact['ball_on_floor'] and self.ball_position()[2] >= self.initial_ball_position[2] + self.lift_height
                self.held_seconds = self.held_seconds + self.config.timestep * 10 if valid else 0.0
        self.held = int((self.held_seconds + 1e-8) / .2)
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
            raise ValueError('小球仿真状态非有限值，停止训练')

    def contact_state(self):
        model, data = self._state()
        touching = set()
        jaw_forces = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body): 0.0 for body in self.jaws}
        ball_on_floor = False
        arm_floor_force = 0.0
        for index, contact in enumerate(data.contact):
            if contact.efc_address < 0 or contact.dist > 0:
                continue
            force = np.zeros(6)
            mujoco.mj_contactForce(model, data, index, force)
            normal = float(force[0])
            if normal <= .01:
                continue
            geoms = (contact.geom1, contact.geom2)
            if self.ball_geom in geoms:
                other = contact.geom2 if contact.geom1 == self.ball_geom else contact.geom1
                body = int(model.geom_bodyid[other])
                if body in self.jaws:
                    touching.add(body)
                    jaw_forces[mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body)] += normal
                if other == self.floor_geom:
                    ball_on_floor = True
            elif self.floor_geom in geoms:
                other = contact.geom2 if contact.geom1 == self.floor_geom else contact.geom1
                body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[other]))
                if body_name not in ('world', 'base_link', 'xiaoxia_fixed_base'):
                    arm_floor_force += normal
        return {'both_jaws': len(touching) == 2, 'jaw_forces': jaw_forces, 'ball_on_floor': ball_on_floor, 'arm_floor_force': arm_floor_force}

    def snapshot(self):
        return {'joint_positions': self.read_observation().joint_positions, 'ball_position': self.ball_position().tolist(),
                'ball_radius': self.radius, 'floor_z': self.floor_z, 'episode_index': self.episode_index,
                'spawn_position': self.spawn_position.tolist(), 'held_seconds': self.held_seconds,
                'phase': self.phases.name, 'curriculum_level': getattr(self, 'curriculum_level', 2),
                'ball_visible': self.ball_visible, 'contacts': self.contact_state(), 'reward_terms': self.last_reward_terms, 'physical': False}

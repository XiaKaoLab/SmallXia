"""SO-101 小球抓取物理环境：独立状态、接触奖励和持续夹持抬升判定。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from copy import copy
from xml.etree import ElementTree as ET

import mujoco
import numpy as np

from ..contracts import Action
from ..safety import JOINTS
from ..simulation.world import MujocoSimulation, SimulationConfig


class BallPickupEnvironment(MujocoSimulation):
    radius = 0.015
    episode_steps = 100

    def extend_scene(self, mjcf):
        world = mjcf.find('worldbody')
        ET.SubElement(world, 'geom', name='pickup_floor', type='plane', size='1 1 .05',
                      pos='0 0 -.003', friction='1 .01 .001', rgba='.8 .85 .82 1')
        ball = ET.SubElement(world, 'body', name='pickup_ball', pos='.2 0 .015')
        ET.SubElement(ball, 'freejoint', name='pickup_ball_free')
        ET.SubElement(ball, 'geom', name='pickup_ball_geom', type='sphere', size=str(self.radius),
                      mass='.012', friction='1.5 .02 .002', condim='4', rgba='1 .35 .15 1')
        gripper = mjcf.find(".//body[@name='gripper_link']")
        if gripper is None:
            raise ValueError('URDF 缺少 gripper_link，无法定位抓取点')
        ET.SubElement(gripper, 'site', name='pickup_tip', pos='-.0079 -.000218121 -.0981274', size='.003')

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
            env.reset_episode()
            environments.append(env)
        return environments

    def reset_episode(self):
        super().reset()
        model, data = self._state()
        address = model.jnt_qposadr[self.ball_joint]
        data.qpos[address:address + 3] = [self.random.uniform(.16, .23), self.random.uniform(-.05, .05), self.radius]
        data.qpos[address + 3:address + 7] = [1, 0, 0, 0]
        mujoco.mj_forward(model, data)
        self.steps = self.held = 0
        self.return_ = 0.0
        self.previous_distance = float(np.linalg.norm(self.ball_position() - data.site_xpos[self.tip]))
        return self.state()

    def ball_position(self):
        return self._data.geom_xpos[self.ball_geom].copy()

    def state(self):
        model, data = self._state()
        q = [data.qpos[model.jnt_qposadr[self._joints[name]]] for name in JOINTS]
        velocity = [data.qvel[model.jnt_dofadr[self._joints[name]]] for name in JOINTS]
        ball = self.ball_position()
        return np.asarray([*q, *velocity, *ball, *(ball - data.site_xpos[self.tip])], dtype=np.float32)

    def advance(self, action):
        current = self.read_observation().joint_positions
        targets = {name: float(np.clip(current[name] + float(action[index]) * .08,
                   self.limits.joints[name].lower, self.limits.joints[name].upper)) for index, name in enumerate(JOINTS)}
        self.send_action(Action(targets))
        super().step(100)
        model, data = self._state()
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
            raise ValueError('小球仿真状态非有限值，停止训练')
        touching = set()
        for contact in data.contact:
            if contact.dist > 0 or self.ball_geom not in (contact.geom1, contact.geom2):
                continue
            other = contact.geom2 if contact.geom1 == self.ball_geom else contact.geom1
            body = int(model.geom_bodyid[other])
            if body in self.jaws:
                touching.add(body)
        ball = self.ball_position()
        distance = float(np.linalg.norm(ball - data.site_xpos[self.tip]))
        lifted = float(np.clip((ball[2] - self.radius) / .05, 0, 1))
        grasped = len(touching) == 2
        self.held = self.held + 1 if grasped and lifted >= 1 else 0
        success = self.held >= 5  # 双指接触且抬升 5cm，连续保持 1 秒。
        reward = 10 * (self.previous_distance - distance) - .01 + .1 * len(touching) + (lifted if grasped else 0) + (10 if success else 0)
        self.previous_distance = distance
        self.return_ += reward
        self.steps += 1
        terminated = success or ball[2] < -.02 or float(np.linalg.norm(ball[:2])) > .6
        truncated = self.steps >= self.episode_steps and not terminated
        return self.state(), float(reward), bool(terminated), bool(truncated), bool(success)

    def snapshot(self):
        return {'joint_positions': self.read_observation().joint_positions, 'ball_position': self.ball_position().tolist(),
                'ball_radius': self.radius, 'physical': False}

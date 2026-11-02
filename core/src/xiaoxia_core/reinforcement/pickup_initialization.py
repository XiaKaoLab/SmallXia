"""随机采样抓球回合的机械臂初始姿态，过滤穿透接触并同步位置控制器。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import numpy as np

from ..safety import JOINTS


class PickupInitialization:
    # 在参考姿态附近采样，避免直接在全关节范围内生成折叠或不可达状态。
    spans = (.55, .35, .45, .4, .6, .25)

    @classmethod
    def apply(cls, env):
        model, data = env._state()
        reference = dict(env.read_observation().joint_positions)
        for _ in range(128):
            positions = {}
            for name, span in zip(JOINTS, cls.spans):
                joint = env._joints[name]
                lower, upper = model.jnt_range[joint]
                center = .55 if name == 'gripper' else reference[name]
                positions[name] = float(env.random.uniform(max(lower + .01, center - span),
                                                          min(upper - .01, center + span)))
            env.set_kinematic_pose(positions)
            if cls.clear(env):
                return positions
        raise ValueError('无法采样到无穿透的随机初始姿态，停止本回合初始化')

    @staticmethod
    def clear(env):
        model, data = env._state()
        for index in range(data.ncon):
            contact = data.contact[index]
            if contact.dist >= 0:
                continue
            # 小球静置地面的接触属于合法初态。
            if {int(contact.geom1), int(contact.geom2)} == {env.ball_geom, env.floor_geom}:
                continue
            return False
        return np.isfinite(data.qpos).all() and np.isfinite(data.qvel).all()

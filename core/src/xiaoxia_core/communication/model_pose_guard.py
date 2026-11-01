"""对显示模型进行关节范围、离散路径与非相邻连杆自碰撞检查。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""

from math import ceil, pi
from pathlib import Path

import mujoco

from ..simulation.world import MujocoSimulation, SimulationConfig


class ModelPoseGuard:
    """MuJoCo 网格凸包检查；不是实机碰撞认证或连续碰撞检测。"""

    def __init__(self, urdf: Path) -> None:
        self.simulation = MujocoSimulation(SimulationConfig(urdf))
        self.simulation.connect()
        self.model, self.data = self.simulation._state()
        self.indices = {mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, i):
                        int(self.model.jnt_qposadr[i]) for i in range(self.model.njnt)}

    def assert_pose(self, positions: dict[str, float]) -> None:
        self.simulation.limits.validate(positions)
        for name, value in positions.items():
            self.data.qpos[self.indices[name]] = value
        mujoco.mj_forward(self.model, self.data)
        for contact in self.data.contact:
            # 容忍网格制造缝隙/数值噪声 0.5 mm，不排除远端连杆碰撞。
            if contact.dist < -0.0005:
                names = [mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_BODY,
                                         int(self.model.geom_bodyid[g])) for g in (contact.geom1, contact.geom2)]
                raise ValueError(f"姿态自碰撞：{names[0]} / {names[1]}，到达碰撞边界")

    def assert_path(self, start: dict[str, float], target: dict[str, float]) -> None:
        self.simulation.limits.validate(target)
        steps = max(1, ceil(max(abs(target[name] - start[name]) for name in start) / (pi / 180)))
        for step in range(steps + 1):
            self.assert_pose({name: start[name] + (target[name] - start[name]) * step / steps for name in start})


    def limit_path(self, start: dict[str, float], target: dict[str, float]) -> tuple[dict[str, float], str]:
        self.simulation.limits.validate(target)
        self.assert_pose(start)
        steps = max(1, ceil(max(abs(target[name] - start[name]) for name in start) / (pi / 180)))
        interpolate = lambda fraction: {name: start[name] + (target[name] - start[name]) * fraction for name in start}
        previous = 0.0
        for step in range(1, steps + 1):
            try:
                self.assert_pose(interpolate(step / steps))
            except ValueError as error:
                low, high = previous, step / steps
                for _ in range(10):
                    middle = (low + high) / 2
                    try:
                        self.assert_pose(interpolate(middle))
                        low = middle
                    except ValueError:
                        high = middle
                return interpolate(max(0.0, low - 0.0001)), str(error)
            previous = step / steps
        return dict(target), ""

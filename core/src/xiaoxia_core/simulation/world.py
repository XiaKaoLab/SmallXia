"""加载 URDF 并提供显式步进和关节位置控制，仅作用于仿真。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from xml.etree import ElementTree

import mujoco

from ..communication import RobotTransport
from ..contracts import Action, Observation


@dataclass(frozen=True)
class SimulationConfig:
    urdf_path: Path
    timestep: float = 0.002
    position_gain: float = 10.0
    damping_gain: float = 0.5
    max_torque: float = 1.0

    def __post_init__(self) -> None:
        for value in (self.timestep, self.position_gain, self.damping_gain, self.max_torque):
            if not isfinite(value) or value <= 0:
                raise ValueError("仿真步长、增益与力矩上限必须为有限正数")


class MujocoSimulation(RobotTransport):
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self._model: mujoco.MjModel | None = None
        self._data: mujoco.MjData | None = None
        self._joints: dict[str, int] = {}
        self._targets: dict[str, float] = {}

    def connect(self) -> None:
        if self._model is not None:
            raise RuntimeError("仿真已连接")
        path = self.config.urdf_path.resolve(strict=True)
        root = ElementTree.parse(path).getroot()
        if root.tag != "robot":
            raise ValueError("需要 URDF robot 文件")
        extension = root.find("mujoco")
        if extension is None:
            extension = ElementTree.SubElement(root, "mujoco")
        compiler = extension.find("compiler")
        if compiler is None:
            compiler = ElementTree.SubElement(extension, "compiler")
        compiler.set("meshdir", path.parent.as_posix())
        compiler.set("strippath", "false")
        compiler.set("discardvisual", "false")
        model = mujoco.MjModel.from_xml_string(ElementTree.tostring(root, encoding="unicode"))
        model.opt.timestep = self.config.timestep
        joints: dict[str, int] = {}
        for index in range(model.njnt):
            if model.jnt_type[index] != mujoco.mjtJoint.mjJNT_HINGE:
                raise ValueError("当前仿真适配器仅支持旋转关节")
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, index)
            if name is None:
                raise ValueError("关节必须命名")
            joints[name] = index
        if not joints:
            raise ValueError("模型未包含可控制关节")
        self._model, self._data, self._joints = model, mujoco.MjData(model), joints
        self.reset()

    def disconnect(self) -> None:
        self._model = self._data = None
        self._joints.clear()
        self._targets.clear()

    def _state(self) -> tuple[mujoco.MjModel, mujoco.MjData]:
        if self._model is None or self._data is None:
            raise RuntimeError("请先连接仿真")
        return self._model, self._data

    def reset(self) -> None:
        model, data = self._state()
        mujoco.mj_resetData(model, data)
        for index in self._joints.values():
            if model.jnt_limited[index]:
                lower, upper = model.jnt_range[index]
                data.qpos[model.jnt_qposadr[index]] = min(max(0.0, lower), upper)
        mujoco.mj_forward(model, data)
        self._targets = dict(self.read_observation().joint_positions)

    def read_observation(self) -> Observation:
        model, data = self._state()
        return Observation(
            timestamp_ns=round(data.time * 1_000_000_000),
            joint_positions={
                name: float(data.qpos[model.jnt_qposadr[index]])
                for name, index in self._joints.items()
            },
        )

    def send_action(self, action: Action) -> None:
        model, _ = self._state()
        for name, target in action.joint_positions.items():
            if name not in self._joints:
                raise ValueError(f"未知关节: {name}")
            index = self._joints[name]
            if model.jnt_limited[index]:
                lower, upper = model.jnt_range[index]
                if not lower <= target <= upper:
                    raise ValueError(f"关节目标超出 URDF 限位: {name}")
        self._targets.update(action.joint_positions)

    def step(self, count: int = 1) -> Observation:
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("步数必须为正整数")
        model, data = self._state()
        for _ in range(count):
            data.qfrc_applied[:] = 0
            for name, target in self._targets.items():
                index = self._joints[name]
                qpos, dof = model.jnt_qposadr[index], model.jnt_dofadr[index]
                torque = (
                    self.config.position_gain * (target - data.qpos[qpos])
                    - self.config.damping_gain * data.qvel[dof]
                )
                data.qfrc_applied[dof] = min(max(torque, -self.config.max_torque), self.config.max_torque)
            mujoco.mj_step(model, data)
        return self.read_observation()

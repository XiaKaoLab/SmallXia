"""加载 URDF 并提供显式步进和关节位置控制，仅作用于仿真。
Created on 2026-11-01; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

import mujoco

from ..communication import RobotTransport
from ..contracts import Action, Observation
from ..safety import JointLimits


@dataclass(frozen=True)
class SimulationConfig:
    urdf_path: Path
    timestep: float = 0.002
    position_gain: float = 10.0
    damping_gain: float = 0.5
    max_torque: float = 1.0
    max_velocity: float = 0.5

    def __post_init__(self) -> None:
        for value in (self.timestep, self.position_gain, self.damping_gain, self.max_torque, self.max_velocity):
            if not isfinite(value) or value <= 0:
                raise ValueError("仿真步长、增益与力矩上限必须为有限正数")


class MujocoSimulation(RobotTransport):
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self._model: mujoco.MjModel | None = None
        self._data: mujoco.MjData | None = None
        self._joints: dict[str, int] = {}
        self._targets: dict[str, float] = {}
        self._setpoints: dict[str, float] = {}

    def connect(self) -> None:
        if self._model is not None:
            raise RuntimeError("仿真已连接")
        path = self.config.urdf_path.resolve(strict=True)
        root = ElementTree.parse(path).getroot()
        if root.tag != "robot":
            raise ValueError("需要 URDF robot 文件")
        self.prepare_urdf(root, path)
        extension = root.find("mujoco")
        if extension is None:
            extension = ElementTree.SubElement(root, "mujoco")
        compiler = extension.find("compiler")
        if compiler is None:
            compiler = ElementTree.SubElement(extension, "compiler")
        # MuJoCo 原生文件加载在 Windows 中文路径下可能失败；网格改用内存 VFS。
        assets: dict[str, bytes] = {}
        filenames: dict[Path, str] = {}
        for mesh in root.findall(".//mesh"):
            source = (path.parent / mesh.attrib["filename"]).resolve(strict=True)
            if not source.is_relative_to(path.parent):
                raise ValueError("网格文件必须位于模型目录中")
            if source not in filenames:
                name = f"mesh_{len(filenames)}{source.suffix}"
                filenames[source] = name
                assets[name] = source.read_bytes()
            mesh.set("filename", filenames[source])
        compiler.set("meshdir", "")
        compiler.set("strippath", "false")
        compiler.set("discardvisual", "false")
        # 保留固定底座，避免融合到 world 后相邻底座/肩轴被误作自碰撞。
        compiler.set("fusestatic", "false")
        model = mujoco.MjModel.from_xml_string(ElementTree.tostring(root, encoding="unicode"), assets=assets)
        # URDF 导入仍可能把根 link 直接放在 world，父子碰撞过滤不覆盖 world。
        # 用等价 MJCF 固定 body 包住根几何和子链，保留几何/惯量/关节范围。
        with TemporaryDirectory(prefix="xiaoxia-mjcf-") as temporary:
            canonical = Path(temporary) / "model.xml"
            mujoco.mj_saveLastXML(str(canonical), model)
            mjcf = ElementTree.parse(canonical).getroot()
        world = mjcf.find("worldbody")
        if world is not None and world.findall("geom"):
            base = ElementTree.Element("body", {"name": "xiaoxia_fixed_base"})
            for node in list(world):
                world.remove(node)
                base.append(node)
            world.append(base)
            mjcf_compiler = mjcf.find("compiler")
            if mjcf_compiler is None:
                mjcf_compiler = ElementTree.SubElement(mjcf, "compiler")
            mjcf_compiler.set("fusestatic", "false")
            mjcf_compiler.set("meshdir", "")
        # 固定底座焊接到 world 时默认父子过滤仍不生效，显式排除相邻 link 接触。
        # 仅排除 URDF 中通过关节直接相连的零件，其他自碰撞继续启用。
        contact = mjcf.find("contact")
        if contact is None:
            contact = ElementTree.SubElement(mjcf, "contact")
        for joint in root.findall("joint"):
            parent, child = joint.find("parent"), joint.find("child")
            if parent is not None and child is not None:
                first, second = parent.attrib["link"], child.attrib["link"]
                if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, first) > 0 and mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, second) > 0:
                    ElementTree.SubElement(contact, "exclude", {"body1": first, "body2": second})
        self.extend_scene(mjcf)
        model = mujoco.MjModel.from_xml_string(ElementTree.tostring(mjcf, encoding="unicode"), assets=assets)
        model.opt.timestep = self.config.timestep
        model.opt.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
        # 阻尼交给隐式求解器，避免小惯量腕轴上显式 D 项导致数值不稳定。
        model.dof_damping[:] += self.config.damping_gain
        self.limits = JointLimits.from_urdf(path)
        joints: dict[str, int] = {}
        for index in range(model.njnt):
            if model.jnt_type[index] == mujoco.mjtJoint.mjJNT_FREE:
                continue  # 场景物体自由关节不属于机械臂控制轴。
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

    def extend_scene(self, mjcf: ElementTree.Element) -> None:
        """子类可在编译前添加任务物体；默认保持纯机械臂场景。"""

    def prepare_urdf(self, root: ElementTree.Element, path: Path) -> None:
        """子类可替换碰撞描述；原始 URDF 和视觉模型保持不变。"""

    def disconnect(self) -> None:
        self._model = self._data = None
        self._joints.clear()
        self._targets.clear()
        self._setpoints.clear()

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
        self._setpoints = dict(self._targets)

    def set_kinematic_pose(self, positions: dict[str, float]) -> None:
        """仅供仿真初始化或脚本主臂输入，不计作动力学运动验证。"""
        model, data = self._state()
        self.limits.validate(positions)
        for name, index in self._joints.items():
            data.qpos[model.jnt_qposadr[index]] = positions[name]
        data.qvel[:] = 0
        mujoco.mj_forward(model, data)
        self._targets, self._setpoints = dict(positions), dict(positions)

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

    def diagnostics(self) -> dict:
        model, data = self._state()
        return {
            "time": float(data.time), "contacts": int(data.ncon),
            "joint_ranges": {name: [float(value) for value in model.jnt_range[index]] for name, index in self._joints.items()},
            "joint_velocities": {name: float(data.qvel[model.jnt_dofadr[index]]) for name, index in self._joints.items()},
            "applied_torques": {name: float(data.qfrc_applied[model.jnt_dofadr[index]]) for name, index in self._joints.items()},
        }

    def step(self, count: int = 1) -> Observation:
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("步数必须为正整数")
        model, data = self._state()
        for _ in range(count):
            data.qfrc_applied[:] = 0
            for name, target in self._targets.items():
                index = self._joints[name]
                qpos, dof = model.jnt_qposadr[index], model.jnt_dofadr[index]
                limit = self.limits.joints[name]
                increment = min(self.config.max_velocity, limit.velocity) * self.config.timestep
                previous = self._setpoints[name]
                self._setpoints[name] = previous + min(max(target - previous, -increment), increment)
                torque = self.config.position_gain * (self._setpoints[name] - data.qpos[qpos]) + data.qfrc_bias[dof]
                effort = min(self.config.max_torque, limit.effort)
                data.qfrc_applied[dof] = min(max(torque, -effort), effort)
            mujoco.mj_step(model, data)
        return self.read_observation()

"""验证六关节弧度、URDF 范围和命令速度；不将模型参数冒充实测限位。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from xml.etree import ElementTree

from ..contracts import Action

JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")


@dataclass(frozen=True)
class JointLimit:
    lower: float
    upper: float
    velocity: float
    effort: float

    def __post_init__(self) -> None:
        if not all(isfinite(value) for value in (self.lower, self.upper, self.velocity, self.effort)):
            raise ValueError("关节限位必须有限")
        if self.lower >= self.upper or min(self.velocity, self.effort) <= 0:
            raise ValueError("关节限位区间、速度或力矩无效")


class JointLimits:
    def __init__(self, joints: dict[str, JointLimit]) -> None:
        if set(joints) != set(JOINTS):
            raise ValueError("必须包含 SO 系列全部六关节")
        self.joints = dict(joints)

    @classmethod
    def from_urdf(cls, path: Path) -> "JointLimits":
        joints = {}
        for node in ElementTree.parse(path).getroot().findall("joint"):
            if node.get("type") == "fixed":
                continue
            limit = node.find("limit")
            if node.get("type") != "revolute" or limit is None:
                raise ValueError("只支持有明确限位的旋转关节")
            joints[node.attrib["name"]] = JointLimit(*(float(limit.attrib[key]) for key in ("lower", "upper", "velocity", "effort")))
        return cls(joints)

    def validate(self, positions: dict[str, float], tolerance: float = 0.0) -> None:
        if not isfinite(tolerance) or tolerance < 0:
            raise ValueError("限位容差无效")
        if set(positions) != set(JOINTS):
            raise ValueError("目标或观测必须包含且仅包含六关节")
        for name, position in positions.items():
            limit = self.joints[name]
            if not isfinite(position) or not limit.lower - tolerance <= position <= limit.upper + tolerance:
                raise ValueError(f"{name} 超出范围 [{limit.lower}, {limit.upper}] rad: {position}")

    def constrain(self, desired: Action, current: dict[str, float], dt: float, max_velocity: float) -> Action:
        self.validate(desired.joint_positions)
        self.validate(current)
        if not isfinite(dt) or dt <= 0 or not isfinite(max_velocity) or max_velocity <= 0:
            raise ValueError("控制周期与速度上限必须为有限正数")
        return Action({name: current[name] + max(-min(limit.velocity, max_velocity) * dt,
                     min(min(limit.velocity, max_velocity) * dt, desired.joint_positions[name] - current[name]))
                       for name, limit in self.joints.items()})

    def midpoint(self) -> dict[str, float]:
        return {name: (limit.lower + limit.upper) / 2 for name, limit in self.joints.items()}

"""将实测编码器范围和独立 URDF 零点映射相交，避免百分比/角度混用。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import json
from dataclasses import dataclass
from math import ceil, floor, isfinite, pi
from pathlib import Path

from ..safety import JOINTS, JointLimit, JointLimits


@dataclass(frozen=True)
class EncoderJoint:
    id: int
    homing_offset: int
    range_min: int
    range_max: int
    zero_tick: float
    direction: int
    ticks_per_turn: int = 4095

    def __post_init__(self) -> None:
        if self.direction not in (-1, 1) or not isfinite(self.zero_tick):
            raise ValueError("编码器方向/零点无效")
        if not 0 <= self.range_min < self.range_max <= 4095 or self.ticks_per_turn != 4095:
            raise ValueError("仅支持与当前 LeRobot STS3215 一致的 4095 刻度映射")

    def angle(self, tick: float) -> float:
        return self.direction * (tick - self.zero_tick) * 2 * pi / self.ticks_per_turn

    def tick(self, angle: float) -> int:
        return round(self.zero_tick + self.direction * angle * self.ticks_per_turn / (2 * pi))


class ArmCalibration:
    def __init__(self, joints: dict[str, EncoderJoint], urdf_limits: JointLimits, margin_rad: float) -> None:
        if set(joints) != set(JOINTS) or not isfinite(margin_rad) or margin_rad <= 0:
            raise ValueError("需要完整六轴映射及正的限位余量")
        self.joints = joints
        limits = {}
        self.tick_bounds: dict[str, tuple[int, int]] = {}
        for name, joint in joints.items():
            model = urdf_limits.joints[name]
            angles = sorted((joint.angle(joint.range_min), joint.angle(joint.range_max)))
            lower, upper = max(model.lower, angles[0]) + margin_rad, min(model.upper, angles[1]) - margin_rad
            if lower >= upper:
                raise ValueError(f"校准与模型区间不相交: {name}")
            endpoints = sorted(joint.zero_tick + joint.direction * angle * 4095 / (2 * pi) for angle in (lower, upper))
            low_tick, high_tick = ceil(endpoints[0]), floor(endpoints[1])
            if low_tick >= high_tick:
                raise ValueError(f"校准与模型没有有效交集: {name}")
            self.tick_bounds[name] = (low_tick, high_tick)
            actual = sorted((joint.angle(low_tick), joint.angle(high_tick)))
            limits[name] = JointLimit(actual[0], actual[1], model.velocity, model.effort)
        self.limits = JointLimits(limits)

    @classmethod
    def load(cls, calibration: Path, mapping: Path, urdf_limits: JointLimits, margin_rad: float = 0.035) -> "ArmCalibration":
        raw = json.loads(Path(calibration).read_text(encoding="utf-8"))
        model_map = json.loads(Path(mapping).read_text(encoding="utf-8"))
        if model_map.get("verified") is not True:
            raise ValueError("URDF 零点/方向映射必须经实机测量确认 verified=true")
        entries = model_map["joints"]
        joints = {}
        if set(raw) != set(JOINTS) or set(entries) != set(JOINTS):
            raise ValueError("校准或映射缺少六关节")
        for index, name in enumerate(JOINTS, 1):
            item, transform = raw[name], entries[name]
            if item["id"] != index or item.get("drive_mode", 0) != 0:
                raise ValueError(f"电机 ID/驱动方向不符合当前 STS3215 配置: {name}")
            joints[name] = EncoderJoint(index, item["homing_offset"], item["range_min"], item["range_max"], transform["zero_tick"], transform["direction"])
        return cls(joints, urdf_limits, margin_rad)

    def angles(self, ticks: dict[str, int]) -> dict[str, float]:
        if set(ticks) != set(JOINTS):
            raise ValueError("编码器反馈不完整")
        positions = {name: self.joints[name].angle(value) for name, value in ticks.items()}
        self.limits.validate(positions)
        return positions

    def ticks(self, positions: dict[str, float]) -> dict[str, int]:
        self.limits.validate(positions)
        result = {name: self.joints[name].tick(value) for name, value in positions.items()}
        if any(not self.tick_bounds[name][0] <= tick <= self.tick_bounds[name][1] for name, tick in result.items()):
            raise ValueError("量化后编码器目标越界")
        return result

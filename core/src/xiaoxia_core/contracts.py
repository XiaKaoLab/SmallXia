"""模块间共享的观测与动作数据契约，关节位置使用弧度。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from dataclasses import dataclass, field
from math import isfinite


@dataclass(frozen=True)
class Observation:
    timestamp_ns: int
    joint_positions: dict[str, float]
    image_paths: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns 必须非负")
        if not self.joint_positions or not all(
            isfinite(value) for value in self.joint_positions.values()
        ):
            raise ValueError("观测必须包含有限的关节位置")


@dataclass(frozen=True)
class Action:
    joint_positions: dict[str, float]

    def __post_init__(self) -> None:
        if not self.joint_positions or not all(
            isfinite(value) for value in self.joint_positions.values()
        ):
            raise ValueError("动作必须包含有限的关节位置")

"""固定编码器零点到 URDF 关节角度的只读显示映射，不进行相对增量或半圈折返。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from dataclasses import dataclass
from math import isfinite, pi

from ..safety import JOINTS


@dataclass(frozen=True)
class DisplayJointMap:
    zero_ticks: dict[str, float]
    directions: dict[str, int]
    ticks_per_turn: int = 4095

    def __post_init__(self):
        if set(self.zero_ticks) != set(JOINTS) or any(not isfinite(v) for v in self.zero_ticks.values()):
            raise ValueError('需要六轴固定零点')
        if set(self.directions) != set(JOINTS) or any(v not in (-1, 1) for v in self.directions.values()):
            raise ValueError('需要六轴方向')

    @classmethod
    def from_reference(cls, ticks, angles, directions):
        # 零点允许在编码器量程外；不能对结果取模，否则会丢失关节的绝对分支。
        return cls({name: ticks[name] - directions[name] * angles[name] * 4095 / (2 * pi)
                    for name in JOINTS}, dict(directions))

    def angles(self, ticks):
        if set(ticks) != set(JOINTS) or any(not isfinite(v) or not 0 <= v <= 4095 for v in ticks.values()):
            raise ValueError('编码器超出单圈位置范围，请检查电机模式和零点')
        return {name: self.directions[name] * (ticks[name] - self.zero_ticks[name])
                * 2 * pi / self.ticks_per_turn for name in JOINTS}

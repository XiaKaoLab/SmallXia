"""在无实体主臂时提供键盘虚拟主臂，启动目标取自从臂当前姿态。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import sys
from time import monotonic_ns

from ..communication import RobotTransport
from ..contracts import Action, Observation
from ..safety import JOINTS, JointLimits


class KeyboardLeader(RobotTransport):
    def __init__(self, follower: RobotTransport, limits: JointLimits, increment: float = 0.01) -> None:
        if not 0 < increment <= 0.02:
            raise ValueError("键盘步幅必须在 (0, 0.02] rad 内")
        self.follower, self.limits, self.increment = follower, limits, increment
        self._positions: dict[str, float] | None = None
        self._axis = 0

    def connect(self) -> None:
        if sys.platform != "win32" or not sys.stdin.isatty():
            raise RuntimeError("键盘主臂需要 Windows 交互终端")
        self._positions = dict(self.follower.read_observation().joint_positions)
        self.limits.validate(self._positions)
        print("键盘主臂：1–6 选择关节，+/- 微调，空格同步从臂当前位置，Q 停止。")

    def disconnect(self) -> None:
        self._positions = None

    def read_observation(self) -> Observation:
        import msvcrt
        if self._positions is None:
            raise RuntimeError("键盘主臂未连接")
        while msvcrt.kbhit():
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                msvcrt.getwch()
            elif key in "123456":
                self._axis = int(key) - 1
                print(f"当前关节: {JOINTS[self._axis]}")
            elif key.lower() == "q":
                raise KeyboardInterrupt
            elif key == " ":
                self._positions = dict(self.follower.read_observation().joint_positions)
            elif key in ("+", "=", "-"):
                name = JOINTS[self._axis]
                limit = self.limits.joints[name]
                target = self._positions[name] + (self.increment if key != "-" else -self.increment)
                self._positions[name] = min(max(target, limit.lower), limit.upper)
        self.limits.validate(self._positions)
        return Observation(monotonic_ns(), dict(self._positions))

    def send_action(self, action: Action) -> None:
        raise RuntimeError("键盘主臂是输入源，不接收设备动作")

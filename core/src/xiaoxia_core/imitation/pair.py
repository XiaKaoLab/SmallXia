"""主臂示教到从臂的有界关节映射，记录实际发送的目标。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from contextlib import ExitStack
from types import TracebackType

from ..communication import RobotTransport
from ..contracts import Action, Observation
from ..safety import JointLimits


class LeaderFollowerPair:
    def __init__(self, leader: RobotTransport, follower: RobotTransport, limits: JointLimits, fps: int = 30, max_velocity: float = 0.25) -> None:
        if leader is follower or fps < 1:
            raise ValueError("主从必须为独立设备，fps 必须为正数")
        if getattr(leader, "port", None) is not None and getattr(leader, "port") == getattr(follower, "port", None):
            raise ValueError("主从不能使用同一个串口")
        self.leader, self.follower, self.limits = leader, follower, limits
        self.fps, self.max_velocity = fps, max_velocity
        self._stack: ExitStack | None = None

    def connect(self) -> None:
        if self._stack is not None:
            raise RuntimeError("主从已经连接")
        with ExitStack() as stack:
            stack.enter_context(self.follower)
            stack.enter_context(self.leader)
            self._stack = stack.pop_all()

    def capture(self) -> tuple[Observation, Action]:
        if self._stack is None:
            raise RuntimeError("请先连接主从臂")
        desired = Action(self.leader.read_observation().joint_positions)
        observation = self.follower.read_observation()
        command = self.limits.constrain(desired, observation.joint_positions, 1 / self.fps, self.max_velocity)
        self.follower.send_action(command)
        applied = getattr(self.follower, "applied_action", command)
        return observation, applied

    def disconnect(self) -> None:
        stack, self._stack = self._stack, None
        if stack is not None:
            stack.close()

    def __enter__(self) -> "LeaderFollowerPair":
        self.connect()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None) -> None:
        self.disconnect()

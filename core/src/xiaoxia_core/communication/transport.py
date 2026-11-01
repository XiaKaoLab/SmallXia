"""定义设备通信生命周期、观测读取与动作发送接口。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from abc import ABC, abstractmethod
from types import TracebackType

from ..contracts import Action, Observation


class RobotTransport(ABC):
    @abstractmethod
    def connect(self) -> None:
        """建立连接；具体设备适配器负责超时和校准检查。"""

    @abstractmethod
    def disconnect(self) -> None:
        """释放资源；实现必须允许重复调用。"""

    @abstractmethod
    def read_observation(self) -> Observation:
        """读取一帧真实观测，失败应抛出异常。"""

    @abstractmethod
    def send_action(self, action: Action) -> None:
        """发送动作；设备适配器负责限位、速度和使能策略。"""

    def __enter__(self) -> "RobotTransport":
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.disconnect()

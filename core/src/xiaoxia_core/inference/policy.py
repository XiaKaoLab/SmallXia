"""定义策略加载和单帧推理接口，返回动作但不驱动设备。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from abc import ABC, abstractmethod
from pathlib import Path

from ..contracts import Action, Observation


class Policy(ABC):
    @abstractmethod
    def load(self, checkpoint: Path) -> None:
        """加载模型；失败应抛出异常。"""

    @abstractmethod
    def predict(self, observation: Observation) -> Action:
        """根据观测返回预测动作。"""

    @abstractmethod
    def reset(self) -> None:
        """清理上一 episode 的历史状态。"""


class InferenceService:
    def __init__(self, policy: Policy) -> None:
        self._policy = policy
        self._ready = False

    def load(self, checkpoint: Path) -> None:
        self._ready = False
        if not checkpoint.exists():
            raise FileNotFoundError(checkpoint)
        self._policy.load(checkpoint)
        self._policy.reset()
        self._ready = True

    def predict(self, observation: Observation) -> Action:
        if not self._ready:
            raise RuntimeError("请先加载策略模型")
        return self._policy.predict(observation)

    def reset(self) -> None:
        if not self._ready:
            raise RuntimeError("请先加载策略模型")
        self._policy.reset()

"""定义训练配置、算法适配器及任务入口，不伪造训练结果。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    dataset_directory: Path
    output_directory: Path
    epochs: int = 1
    batch_size: int = 32

    def __post_init__(self) -> None:
        if self.epochs < 1 or self.batch_size < 1:
            raise ValueError("epochs 和 batch_size 必须大于零")


@dataclass(frozen=True)
class TrainingResult:
    checkpoint: Path
    metrics: dict[str, float] = field(default_factory=dict)


class Trainer(ABC):
    @abstractmethod
    def train(self, config: TrainingConfig) -> TrainingResult:
        """由具体算法读取数据集、训练并保存模型。"""


class TrainingService:
    def __init__(self, trainer: Trainer) -> None:
        self._trainer = trainer

    def run(self, config: TrainingConfig) -> TrainingResult:
        if not config.dataset_directory.is_dir():
            raise FileNotFoundError(config.dataset_directory)
        config.output_directory.mkdir(parents=True, exist_ok=True)
        return self._trainer.train(config)

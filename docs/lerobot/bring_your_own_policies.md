# 来源

https://hugging-face.cn/docs/lerobot/bring_your_own_policies

# 自定策略集成 (Bring Your Own Policies)

本教程将说明如何将您自定义的策略实现集成到 LeRobot 生态系统中，使您在运行自己的算法时，能够利用 LeRobot 提供的所有训练、评估和部署工具。

## 步骤 1：创建策略包

您的自定义策略应组织为一个可安装的 Python 包，并遵循 LeRobot 的插件约定。

### 包结构

创建一个前缀为 `lerobot_policy_`（重要！）且后接您的策略名称的包

```
lerobot_policy_my_custom_policy/
├── pyproject.toml
└── src/
    └── lerobot_policy_my_custom_policy/
        ├── __init__.py
        ├── configuration_my_custom_policy.py
        ├── modeling_my_custom_policy.py
        └── processor_my_custom_policy.py
```

### 包配置

设置您的 `pyproject.toml`

```
[project]
name = "lerobot_policy_my_custom_policy"
version = "0.1.0"
dependencies = [
    # your policy-specific dependencies
]
requires-python = ">= 3.12"

[build-system]
build-backend = # your-build-backend
requires = # your-build-system
```

## 步骤 2：定义策略配置

创建一个继承自 [`PreTrainedConfig`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/configs/policies.py) 并注册您的策略类型的配置类：以下是一个入门模板，请根据您的策略架构和训练需求自定义参数和方法。

```
# configuration_my_custom_policy.py
from dataclasses import dataclass, field
from lerobot.configs.policies import PreTrainedConfig
from lerobot.optim.optimizers import AdamWConfig
from lerobot.optim.schedulers import CosineDecayWithWarmupSchedulerConfig

@PreTrainedConfig.register_subclass("my_custom_policy")
@dataclass
class MyCustomPolicyConfig(PreTrainedConfig):
    """Configuration class for MyCustomPolicy.

    Args:
        n_obs_steps: Number of observation steps to use as input
        horizon: Action prediction horizon
        n_action_steps: Number of action steps to execute
        hidden_dim: Hidden dimension for the policy network
        # Add your policy-specific parameters here
    """

    horizon: int = 50
    n_action_steps: int = 50
    hidden_dim: int = 256

    optimizer_lr: float = 1e-4
    optimizer_weight_decay: float = 1e-4

    def __post_init__(self):
        super().__post_init__()
        if self.n_action_steps > self.horizon:
            raise ValueError("n_action_steps cannot exceed horizon")

    def validate_features(self) -> None:
        """Validate input/output feature compatibility."""
        if not self.image_features:
            raise ValueError("MyCustomPolicy requires at least one image feature.")
        if self.action_feature is None:
            raise ValueError("MyCustomPolicy requires 'action' in output_features.")

    def get_optimizer_preset(self) -> AdamWConfig:
        return AdamWConfig(lr=self.optimizer_lr, weight_decay=self.optimizer_weight_decay)

    def get_scheduler_preset(self):
        return None

    @property
    def observation_delta_indices(self) -> list[int] | None:
        """Relative timestep offsets the dataset loader provides per observation.

        Return `None` for single-frame policies. For temporal policies that consume
        multiple past or future frames, return a list of offsets, e.g. `[-20, -10, 0, 10]` for
        3 past frames at stride 10 and 1 future frame at stride 10.
        """
        return None

    @property
    def action_delta_indices(self) -> list[int]:
        """Relative timestep offsets for the action chunk the dataset loader returns.
        """
        return list(range(self.horizon))

    @property
    def reward_delta_indices(self) -> None:
        return None
```

## 步骤 3：实现策略类

通过继承 [`PreTrainedPolicy`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/pretrained.py) 来创建您的策略实现

```
# modeling_my_custom_policy.py
import torch
import torch.nn as nn
from typing import Any

from lerobot.policies.pretrained import PreTrainedPolicy
from lerobot.utils.constants import ACTION
from .configuration_my_custom_policy import MyCustomPolicyConfig

class MyCustomPolicy(PreTrainedPolicy):
    config_class = MyCustomPolicyConfig  # must match the string in @register_subclass
    name = "my_custom_policy"

    def __init__(self, config: MyCustomPolicyConfig, dataset_stats: dict[str, Any] = None):
        super().__init__(config, dataset_stats)
        config.validate_features()  # not called automatically by the base class
        self.config = config
        self.model = ...  # your nn.Module here

    def reset(self):
        """Reset episode state."""
        ...

    def get_optim_params(self) -> dict:
        """Return parameters to pass to the optimizer (e.g. with per-group lr/wd)."""
        return {"params": self.parameters()}

    def predict_action_chunk(self, batch: dict[str, torch.Tensor], **kwargs) -> torch.Tensor:
        """Return the full action chunk (B, chunk_size, action_dim) for the current observation."""
        ...

    def select_action(self, batch: dict[str, torch.Tensor], **kwargs) -> torch.Tensor:
        """Return a single action for the current timestep (called at inference)."""
        ...

    def forward(self, batch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        """Compute the training loss.

        `batch["action_is_pad"]` is a bool mask of shape (B, horizon) that marks
        timesteps padded because the episode ended before `horizon` steps, you
        can exclude those from your loss.
        """
        actions = batch[ACTION]
        action_is_pad = batch.get("action_is_pad")
        ...
        return {"loss": ...}
```

## 步骤 4：添加数据处理器

创建处理器函数。具体参考请参阅 [processor\_act.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/act/processor_act.py) 或 [processor\_diffusion.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/diffusion/processor_diffusion.py)。

```
# processor_my_custom_policy.py
from typing import Any
import torch

from lerobot.processor import PolicyAction, PolicyProcessorPipeline


def make_my_custom_policy_pre_post_processors(
    config,
    dataset_stats: dict[str, dict[str, torch.Tensor]] | None = None,
) -> tuple[
    PolicyProcessorPipeline[dict[str, Any], dict[str, Any]],
    PolicyProcessorPipeline[PolicyAction, PolicyAction],
]:
    preprocessor = ...   # build your PolicyProcessorPipeline for inputs
    postprocessor = ...  # build your PolicyProcessorPipeline for outputs
    return preprocessor, postprocessor
```

**重要提示 - 函数命名：** LeRobot 通过名称发现您的处理器。该函数 **必须** 命名为 `make_{policy_name}_pre_post_processors`（与您传递给 `@PreTrainedConfig.register_subclass` 的字符串相匹配）。

## 步骤 5：包初始化

在包的 `__init__.py` 中公开您的类

```
# __init__.py
"""Custom policy package for LeRobot."""

try:
    import lerobot  # noqa: F401
except ImportError:
    raise ImportError(
        "lerobot is not installed. Please install lerobot to use this policy package."
    )

from .configuration_my_custom_policy import MyCustomPolicyConfig
from .modeling_my_custom_policy import MyCustomPolicy
from .processor_my_custom_policy import make_my_custom_policy_pre_post_processors

__all__ = [
    "MyCustomPolicyConfig",
    "MyCustomPolicy",
    "make_my_custom_policy_pre_post_processors",
]
```

## 步骤 6：安装与使用

### 安装您的策略包

```
cd lerobot_policy_my_custom_policy
pip install -e .

# Or install from PyPI if published
pip install lerobot_policy_my_custom_policy
```

### 使用您的策略

安装完成后，您的策略将自动与 LeRobot 的训练和评估工具集成

```
lerobot-train \
    --policy.type my_custom_policy \
    --env.type pusht \
    --steps 200000
```

## 示例与社区贡献

查看这些策略实现示例

* [DiTFlow Policy](https://github.com/danielsanjosepro/lerobot_policy_ditflow) - 采用流匹配（flow-matching）目标的扩散 Transformer 策略。在此示例中尝试：[DiTFlow 示例](https://github.com/danielsanjosepro/test_lerobot_policy_ditflow)

与社区分享你的策略实现吧！ 🤗

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/bring_your_own_policies.mdx)
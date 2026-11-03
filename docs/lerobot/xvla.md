# 来源

https://hugging-face.cn/docs/lerobot/xvla

# X-VLA：首个适用于任何机器人、任何任务的软提示（Soft-Prompted）机器人基础模型

## 概述

多年来，机器人技术一直致力于构建能够遵循人类自然语言指令，并在多种环境和不同机器人本体上灵活作业的智能体。大语言模型（LLM）和视觉语言模型（VLM）的最新突破为我们指明了方向：通过将这些基础模型架构与动作（Action）相结合，将其延伸至具身控制领域。这催生了视觉-语言-动作（VLA）模型的兴起，人们期望单一的通用模型能够将广泛的语义理解能力与强大的操作技能融为一体。

然而，训练此类模型难度巨大。机器人数据分散在不同的平台、传感器、本体和采集协议中。异构性无处不在：不同的机械臂配置、不同的动作空间、不同的摄像机设置、不同的视觉领域以及不同的任务分布。这些不一致性造成了严重的分布偏移，导致预训练不稳定且适应性不可靠。

受元学习（Meta-learning）和提示学习（Prompt learning）的启发，我们提出了一个问题：**“如果 VLA 模型能够像 LLM 学习任务那样，通过提示（Prompts）来学习每个机器人和数据集的结构，会怎样？”**

**X-VLA** 是一种基于软提示（Soft-Prompted）和流匹配（Flow-matching）的 VLA 框架，它将每种硬件配置视为一个“任务”，并使用一组少量的可学习嵌入（Embeddings）对其进行编码。这些**软提示**捕获了本体和领域特定的差异，从多模态融合的最早阶段引导 Transformer。凭借这一机制，X-VLA 能够在统一的架构内调和不同的机器人形态、数据类型和传感器设置。

![XVLA Architecture](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/xvla-architecture.png)

X-VLA 由纯 Transformer 编码器构建，能够随模型规模和数据集多样性自然扩展。在 6 个仿真基准和 3 种真实机器人上的测试表明，软提示在处理硬件和领域差异方面始终优于现有方法。X-VLA-0.9B 在涵盖七个机器人平台的 29 万个片段上进行训练，在第一阶段学习了一种与本体无关的通用策略，并在第二阶段仅通过学习一组新的提示，即可在保持主干网络冻结的情况下高效适应新机器人。

![XVLA Architecture 2](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/xvla-architecture2.png)

在仅调整 1% 参数（900 万）的情况下，X-VLA-0.9B 在 LIBERO 和 Simpler-WidowX 上达到了接近 π₀ 的性能，尽管其**可训练参数减少了 300 倍**。它还在极少量演示的情况下展现了强大的现实世界灵活性，包括在不到两分钟内完成衣物折叠。

![XVLA fold visualization](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/xvla-fold.png)

X-VLA 表明，通用机器人智能不需要越来越复杂的架构，只需要吸收异构性的正确方式。软提示为整合多样化的机器人数据提供了一种简单、可扩展的机制，为实现可适应的、跨本体的机器人基础模型铺平了道路。

## 安装

安装 LeRobot 后，安装 X-VLA 依赖项

```
pip install -e .[xvla]
```

新版本发布后，您将能够执行

```
pip install lerobot[xvla]
```

## 快速开始

### 基本用法

要在您的 LeRobot 配置中使用 X-VLA，请将策略类型指定为

```
policy.type=xvla
```

### 评估预训练检查点（Checkpoints）

使用 LIBERO 进行评估的示例

```
lerobot-eval \
  --policy.path="lerobot/xvla-libero" \
  --env.type=libero \
  --env.task=libero_spatial,libero_goal,libero_10 \
  --env.control_mode=absolute \
  --eval.batch_size=1 \
  --eval.n_episodes=1 \
  --env.episode_length=800 \
  --seed=142
```

## 可用检查点

### 🎯 基础模型

**[lerobot/xvla-base](https://hugging-face.cn/lerobot/xvla-base)**

X-VLA 的 9 亿参数版本，使用精心设计的数据处理和学习方案进行训练。训练流水线包含两个阶段：

* **阶段 I：预训练** - 在来自 Droid、Robomind 和 Agibot 的 29 万个片段上进行预训练，涵盖五个机器人手臂类型（从单臂到双臂设置）的七个平台。通过利用软提示来吸收特定本体的差异，模型学习了一种与本体无关的通用策略。
* **阶段 II：领域适应** - 适应目标领域的部署策略。引入并优化了一组新的软提示，以对新领域的硬件配置进行编码，同时保持预训练的主干网络冻结。

### 仿真检查点

**[lerobot/xvla-libero](https://hugging-face.cn/lerobot/xvla-libero)**

在 LIBERO 基准测试中达到 93% 的成功率。针对仿真任务从基础模型微调而来。

**[lerobot/xvla-widowx](https://hugging-face.cn/lerobot/xvla-widowx)**

在 BridgeData 上进行微调，用于紧凑型 WidowX 平台上的抓取与放置实验。展示了强大的操作能力。

### 🤖 现实世界检查点

**[lerobot/xvla-folding](https://hugging-face.cn/lerobot/xvla-folding)**

一个在高质量 Soft-FOLD 衣物折叠数据集上训练的精密操作模型。在 2 小时的连续衣物折叠任务中达到 100% 的成功率。

**[lerobot/xvla-agibot-world](https://hugging-face.cn/lerobot/xvla-agibot-world)**

针对 AgileX 机器人的精密操作任务进行了优化。

**[lerobot/xvla-google-robot](https://hugging-face.cn/lerobot/xvla-google-robot)**

适配 Google 机器人平台。

## 训练 X-VLA

### 推荐训练配置

在针对新的本体或任务微调 X-VLA 时，我们建议不要冻结 VLM，并将 `policy.dtype=bfloat16` 以避免内存溢出（OOM）错误。

```
lerobot-train \
  --dataset.repo_id=YOUR_DATASET \
  --output_dir=./outputs/xvla_training \
  --job_name=xvla_training \
  --policy.path="lerobot/xvla-base" \
  --policy.repo_id="HF_USER/xvla-your-robot" \
  --policy.dtype=bfloat16 \
  --policy.action_mode=auto \
  --steps=20000 \
  --policy.device=cuda \
  --policy.freeze_vision_encoder=false \
  --policy.freeze_language_encoder=false \
  --policy.train_policy_transformer=true \
  --policy.train_soft_prompts=true \
```

### 训练参数详解

| 参数 | 默认 | 描述 |
| --- | --- | --- |
| `freeze_vision_encoder` | `false` | 不要冻结 VLM 视觉编码器权重 |
| `freeze_language_encoder` | `false` | 不要冻结 VLM 语言编码器权重 |
| `train_policy_transformer` | `true` | 允许策略 Transformer 层进行训练 |
| `train_soft_prompts` | `true` | 允许软提示进行训练 |

**💡 最佳实践**：对于阶段 II 中针对新本体的适应，请勿冻结 VLM 编码器，并同时训练策略 Transformer 和软提示。

### 示例：在双臂机器人上训练

```
lerobot-train \
  --dataset.repo_id=<USER>/bimanual-so100-handover-cube \
  --output_dir=./outputs/xvla_bimanual \
  --job_name=xvla_so101_training \
  --policy.path="lerobot/xvla-base" \
  --policy.dtype=bfloat16 \
  --policy.repo_id="YOUR_USERNAME/xvla-biso101" \
  --steps=3000 \
  --policy.device=cuda \
  --policy.action_mode=so101_bimanual \
  --policy.freeze_vision_encoder=false \
  --policy.freeze_language_encoder=false \
  --policy.train_policy_transformer=true \
  --policy.train_soft_prompts=true
```

💡 **最佳性能：** 如果您拥有充足的计算资源并希望获得最佳的 X-VLA 微调性能，请遵循官方的微调策略。

**🔥 使用自定义学习率方案对所有组件进行全量微调**

为了确保优化稳定，视觉语言模型（VLM）必须以基础学习率的 1/10 进行训练，而所有其他组件使用完整学习率。这种学习率比例对于实现稳健的微调性能至关重要。这已经为您默认配置好了。❕注意

完全匹配官方报告的性能可能需要为软提示添加额外的预热（Warm-up）学习率计划，这可以带来微小的改进。我们鼓励在您的自定义训练流水线中实现这一点以获得最佳结果。

## 核心概念

### 1. 动作模式（Action Modes）

X-VLA 使用**动作注册表（Action Registry）**系统来处理不同的动作空间和本体。`action_mode` 参数定义了动作的处理方式、使用的损失函数以及预测结果的后处理方式。

#### 可用动作模式

| 动作模式 | 动作维度 | 描述 | 用例 |
| --- | --- | --- | --- |
| `ee6d` | 20 | 包含 xyz、6D 旋转和夹爪的末端执行器 | 带有空间控制的双臂设置 |
| `joint` | 14 | 包含夹爪的关节空间控制 | 直接关节控制机器人 |
| `agibot_ee6d` | 20 | 带有 MSE 损失的 AGI-bot 变体 | AGI-bot 平台 |
| `so101_bimanual` | 20 (模型), 12 (真实) | SO101 双臂机器人 | 双臂操作任务 |
| `auto` | 20 (模型), 自动 (真实) | 从数据集中自动检测动作维度 | **推荐**用于新机器人 |

#### 为什么动作模式很重要

当您拥有一个使用 `action_dim=20` 训练的预训练检查点（如 `lerobot/xvla-base`），并且想要在一个具有不同动作维度的数据集（例如双臂的 14 维）上进行训练时，您不能简单地裁剪动作维度。动作模式负责编排：

1. **损失计算**：针对不同动作组件采用不同的损失函数（关节用 MSE，夹爪用 BCE 等）
2. **预处理**：将夹爪通道归零，填充维度
3. **后处理**：对夹爪 Logits 应用 Sigmoid，裁剪填充内容

#### 示例：BimanualSO101 动作空间

`so101_bimanual` 动作模式处理了模型输出（20D）与真实机器人控制（12D）之间的不匹配问题。

```
# Model outputs 20 dimensions for compatibility
dim_action = 20

# Real robot only needs 12 dimensions
# [left_arm (6), right_arm (6)] = [joints (5) + gripper (1)] × 2
REAL_DIM = 12

# Preprocessing: Pad 12D actions to 20D for training
# Postprocessing: Trim 20D predictions to 12D for deployment
```

详情请参阅 [action\_hub.py](https://hugging-face.cn/home/jade_choghari/robot/lerobot/src/lerobot/policies/xvla/action_hub.py) 的实现。

#### 自动动作模式（推荐）

`auto` 动作模式是使用 X-VLA 适配任何机器人的最简便方法。它会自动检测数据集的动作维度并处理填充/裁剪：

```
lerobot-train \
  --policy.path="lerobot/xvla-base" \
  --policy.action_mode=auto \
  --policy.max_action_dim=20 \
  ...
```

**工作原理**

* 从您的数据集中读取 `action_feature.shape[-1]`（例如，Franka 为 7）
* 模型输出 `max_action_dim`（默认为 20）以保持预训练兼容性
* 损失函数**仅在真实维度上计算**：`MSE(pred[:,:,:real_dim], target[:,:,:real_dim])`
* 后处理将输出裁剪回 `real_dim` 以用于机器人控制

这消除了为大多数机器人创建自定义动作模式的需要。

### 2. 领域 ID（Domain IDs）

领域 ID 是针对不同机器人配置和摄像机设置的可学习标识符。它们允许 X-VLA 区分：

* 不同的机器人（机器人 1 与机器人 2）
* 不同的摄像机配置（cam1 与 cam2）
* 不同的组合（Robot1-cam1-cam2 与 Robot1-cam1 与 Robot2-cam1）

#### 设置领域 ID

**训练期间**：默认情况下，常规训练的 domain\_id 设置为 0。

**评估期间**：指定与您的检查点训练配置相匹配的 domain\_id。

```
# Example: LIBERO checkpoint uses domain_id=3
domain_id = 3
```

domain\_id 会通过预处理流水线中的 `XVLAAddDomainIdProcessorStep` 自动添加到观测值中。

`lerobot/xvla-base` 模型已针对以下领域 ID 进行了训练。建议选择与您的机器人/配置最相似的一个。

#### 微调数据集

| 数据集名称 | 领域 ID |
| --- | --- |
| Bridge | 0 |
| RT1 | 1 |
| Calvin | 2 |
| libero | 3 |
| widowx-air | 4 |
| AIR-AGILEX-HQ | 5 |
| robotwin2\_abs\_ee | 6 |
| robotwin2\_clean | 6 |
| robocasa-human | 7 |
| VLABench | 8 |
| AGIBOT-challenge | 9 |
| AIR-AGILEX | 10 |
| AIRBOT | 18 |

### 3. 处理器步骤（Processor Steps）

X-VLA 需要特定的预处理和后处理步骤才能正常运行。

#### 必需的预处理步骤

1. **XVLAImageToFloatProcessorStep**：将图像从 [0, 255] 范围转换为 [0, 1] 范围
2. **XVLAImageNetNormalizeProcessorStep**：应用 ImageNet 标准化（VLM 主干网必需）
3. **XVLAAddDomainIdProcessorStep**：将 domain\_id 添加到观测值中

#### 自定义处理器示例

对于 LIBERO 环境，自定义处理器负责处理特定的观测格式。

```
from lerobot.policies.xvla.processor_xvla import LiberoProcessorStep

processor = LiberoProcessorStep()
# Handles robot_state dictionary, converts rotation matrices to 6D representation
# Applies 180° image rotation for camera convention
```

### 4. 配置参数

X-VLA 的关键配置参数。

```
# Observation and action
n_obs_steps: int = 1          # Number of observation timesteps
chunk_size: int = 32           # Action sequence length
n_action_steps: int = 32       # Number of action steps to execute

# Model architecture
hidden_size: int = 1024        # Transformer hidden dimension
depth: int = 24                # Number of transformer layers
num_heads: int = 16            # Number of attention heads
num_domains: int = 30          # Maximum number of domain IDs
len_soft_prompts: int = 32     # Length of soft prompt embeddings

# Action space
action_mode: str = "ee6d"      # Action space type (use "auto" for auto-detection)
use_proprio: bool = True       # Use proprioceptive state
max_state_dim: int = 32        # Maximum state dimension
max_action_dim: int = 20       # Max action dim for padding (used by "auto" mode)

# Vision
num_image_views: int | None    # Number of camera views
resize_imgs_with_padding: tuple[int, int] | None  # Target image size with padding

# Training
num_denoising_steps: int = 10  # Flow matching denoising steps
```

## 创建自定义动作模式

如果您的机器人具有独特的动作空间，您可以创建自定义动作模式。

### 步骤 1：定义您的动作空间

```
from lerobot.policies.xvla.action_hub import BaseActionSpace, register_action
import torch.nn as nn

@register_action("my_custom_robot")
class MyCustomActionSpace(BaseActionSpace):
    """Custom action space for my robot."""

    dim_action = 15  # Your robot's action dimension
    gripper_idx = (7, 14)  # Gripper channel indices

    def __init__(self):
        super().__init__()
        self.mse = nn.MSELoss()
        self.bce = nn.BCEWithLogitsLoss()

    def compute_loss(self, pred, target):
        """Define your loss computation."""
        # Example: MSE for joints, BCE for grippers
        joints_loss = self.mse(pred[:, :, :7], target[:, :, :7])
        gripper_loss = self.bce(pred[:, :, self.gripper_idx],
                                target[:, :, self.gripper_idx])

        return {
            "joints_loss": joints_loss,
            "gripper_loss": gripper_loss,
        }

    def preprocess(self, proprio, action, mode="train"):
        """Preprocess actions before training."""
        # Example: Zero out grippers in proprioception
        proprio_m = proprio.clone()
        action_m = action.clone() if action is not None else None
        proprio_m[..., self.gripper_idx] = 0.0
        if action_m is not None:
            action_m[..., self.gripper_idx] = 0.0
        return proprio_m, action_m

    def postprocess(self, action):
        """Post-process predictions for deployment."""
        # Example: Apply sigmoid to gripper logits
        action[..., self.gripper_idx] = torch.sigmoid(action[..., self.gripper_idx])
        return action
```

### 步骤 2：使用您的自定义动作模式

```
lerobot-train \
  --policy.action_mode=my_custom_robot \
  --dataset.repo_id=YOUR_DATASET \
  --policy.path="lerobot/xvla-base" \
  ...
```

## 高级主题

### 多摄像机支持

X-VLA 通过 `num_image_views` 参数支持多个摄像机视角。

```
# Configure for 3 camera views
policy.num_image_views=3

# Add empty cameras if you have fewer physical cameras
policy.empty_cameras=1  # Adds 1 zero-padded camera view
```

### 自定义预处理流水线

为您的环境创建自定义预处理流水线。

```
from lerobot.processor import PolicyProcessorPipeline
from lerobot.policies.xvla.processor_xvla import (
    XVLAImageToFloatProcessorStep,
    XVLAImageNetNormalizeProcessorStep,
    XVLAAddDomainIdProcessorStep,
)

# Build custom pipeline
preprocessor = PolicyProcessorPipeline(
    steps=[
        YourCustomProcessorStep(),  # Your custom processing
        XVLAImageToFloatProcessorStep(),  # Required: convert to float
        XVLAImageNetNormalizeProcessorStep(),  # Required: ImageNet norm
        XVLAAddDomainIdProcessorStep(domain_id=5),  # Your domain ID
    ]
)
```

### 处理不同的动作维度

当您的数据集动作维度少于预训练模型时：

**选项 1（推荐）**：使用 `auto` 动作模式

```
# Automatically detects your dataset's action dimension
# Works with any robot without custom code
policy.action_mode=auto
policy.max_action_dim=20  # Match pretrained model
```

**选项 2**：使用带有内置填充的预定义动作模式

```
# Model expects 20D, dataset has 12D
# Action mode handles padding internally
action_mode = "so101_bimanual"  # Pads 12 → 20
```

**选项 3**：创建明确映射维度的自定义动作模式

```
@register_action("my_mapped_action")
class MappedActionSpace(BaseActionSpace):
    dim_action = 20
    REAL_DIM = 12

    def _pad_to_model_dim(self, x):
        # Custom padding logic
        ...
```

## 疑难解答

### 常见问题

**问题**：“动作维度不匹配”

* **解决方案**：检查您的 `action_mode` 是否与机器人的动作空间匹配。如有必要，创建自定义动作模式。

**问题**：“图像值超出 [0, 1] 范围”

* **解决方案**：确保在标准化之前，图像已使用 `XVLAImageToFloatProcessorStep` 进行预处理。

**问题**：“找不到领域 ID”

* **解决方案**：确保 `XVLAAddDomainIdProcessorStep` 包含在具有正确 domain\_id 的预处理流水线中。

**问题**：“在新本体上成功率低”

* **解决方案**:
  1. 验证您的 action\_mode 是否正确
  2. 检查软提示是否正在训练 (`train_soft_prompts=True`)
  3. 确保适当的预处理（ImageNet 标准化、domain\_id）
  4. 考虑增加训练步数

**问题**：“训练期间内存不足”

* **解决方案**:
  1. 减少 `chunk_size`（例如，从 32 减至 16）
  2. 启用梯度检查点（Gradient checkpointing）
  3. 减小批次大小（Batch size）
  4. 冻结更多组件

## 引用

如果您在研究中使用 X-VLA，请引用：

```
@article{zheng2025x,
  title   = {X-VLA: Soft-Prompted Transformer as Scalable Cross-Embodiment Vision-Language-Action Model},
  author  = {Zheng, Jinliang and Li, Jianxiong and Wang, Zhihao and Liu, Dongxiu and Kang, Xirui
             and Feng, Yuchun and Zheng, Yinan and Zou, Jiayin and Chen, Yilun and Zeng, Jia and others},
  journal = {arXiv preprint arXiv:2510.10274},
  year    = {2025}
}
```

## 附加资源

* [X-VLA 论文](https://arxiv.org/pdf/2510.10274)
* [LeRobot 文档](https://github.com/huggingface/lerobot)
* [动作注册表实现](https://github.com/huggingface/lerobot/src/lerobot/policies/xvla/action_hub.py)
* [处理器实现](https://github.com/huggingface/lerobot/src/lerobot/policies/xvla/processor_xvla.py)
* [模型配置](https://github.com/huggingface/lerobot/src/lerobot/policies/xvla/configuration_xvla.py)

## 贡献

我们欢迎贡献！如果您为您的机器人实现了新的动作模式或处理器，请考虑提交 PR 以帮助社区。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/xvla.mdx)
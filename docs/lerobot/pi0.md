# 来源

https://hugging-face.cn/docs/lerobot/pi0

# π₀ (Pi0)

π₀ 是由 Physical Intelligence 开发的一种**用于通用机器人控制的视觉-语言-动作（Vision-Language-Action）模型**。LeRobot 的实现改编自其开源的 [OpenPI](https://github.com/Physical-Intelligence/openpi) 仓库。

## 模型概述

π₀ 是机器人领域的一次突破，是由 [Physical Intelligence](https://www.physicalintelligence.company/blog/pi0) 开发的首个通用机器人基础模型。传统的机器人程序通常是针对重复动作编程的狭义专家，而 π₀ 被设计为一个通用策略，能够理解视觉输入、解释自然语言指令，并在多种任务中控制各种不同的机器人。

![An overview of Pi0](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/lerobot-pi0%20(1).png)

### Physical Intelligence 的愿景

正如 Physical Intelligence 所描述的，虽然 AI 在数字领域（从下棋到药物研发）取得了显著成功，但在物理世界中，人类智能仍然大幅领先于 AI。用莫拉维克悖论（Moravec’s paradox）的话来说，赢得一场国际象棋比赛对 AI 而言是一个“简单”的问题，但折一件衬衫或清理一张桌子则需要解决一些史上最困难的工程问题。π₀ 代表了开发“人工物理智能”的第一步，旨在让用户能够像使用大语言模型一样，简单地要求机器人执行任何他们想要的任务。

### 架构与方法

π₀ 结合了几项关键创新：

* **流匹配 (Flow Matching)**：采用一种新方法，通过流匹配（扩散模型的一种变体）为预训练的 VLM 增强连续动作输出能力
* **跨具身训练 (Cross-Embodiment Training)**：在来自 8 个不同机器人平台的数据上进行训练，包括 UR5e、双臂 UR5e、Franka、双臂 Trossen、双臂 ARX、移动 Trossen 和移动 Fibocom
* **互联网规模预训练 (Internet-Scale Pre-training)**：继承自一个预训练的 3B 参数视觉-语言模型的语义知识
* **高频控制 (High-Frequency Control)**：以高达 50 Hz 的频率输出电机指令，实现实时的灵巧操作

## 安装要求

1. 请遵循我们的[安装指南](installation.md)来安装 LeRobot。
2. 运行以下命令安装 Pi0 依赖项：

   ```
   pip install -e ".[pi]"
   ```

## 训练数据与能力

π₀ 在迄今为止最大的机器人交互数据集上进行训练，结合了三个关键数据源：

1. **互联网规模预训练**：来自网络的视觉-语言数据，用于语义理解
2. **Open X-Embodiment 数据集**：开源的机器人操作数据集
3. **Physical Intelligence 数据集**：涵盖 8 种不同机器人的大规模、多样化灵巧任务数据集

## 用法

要在 LeRobot 中使用 π₀，请指定策略类型为：

```
policy.type=pi0
```

## 训练

对于 π₀ 的训练，您可以使用标准 LeRobot 训练脚本并配合相应的配置

```
lerobot-train \
    --dataset.repo_id=your_dataset \
    --policy.type=pi0 \
    --output_dir=./outputs/pi0_training \
    --job_name=pi0_training \
    --policy.pretrained_path=lerobot/pi0_base \
    --policy.repo_id=your_repo_id \
    --policy.compile_model=true \
    --policy.gradient_checkpointing=true \
    --policy.dtype=bfloat16 \
    --policy.freeze_vision_encoder=false \
    --policy.train_expert_only=false \
    --steps=3000 \
    --policy.device=cuda \
    --batch_size=32
```

### 关键训练参数

* **`--policy.compile_model=true`**：启用模型编译以加快训练速度
* **`--policy.gradient_checkpointing=true`**：显著降低训练期间的内存占用
* **`--policy.dtype=bfloat16`**：使用混合精度训练以提高效率
* **`--batch_size=32`**：训练的批次大小，请根据您的 GPU 显存进行调整
* **`--policy.pretrained_path=lerobot/pi0_base`**：您想要微调的 π₀ 基础模型，选项有：
  + [lerobot/pi0\_base](https://hugging-face.cn/lerobot/pi0_base)
  + [lerobot/pi0\_libero](https://hugging-face.cn/lerobot/pi0_libero) (专门在 Libero 数据集上训练)

### 训练参数详解

| 参数 | 默认 | 描述 |
| --- | --- | --- |
| `freeze_vision_encoder` | `false` | 不要冻结视觉编码器 |
| `train_expert_only` | `false` | 不要冻结 VLM，训练所有参数 |

**💡 提示**：设置 `train_expert_only=true` 会冻结 VLM，仅训练动作专家（action expert）和投影层，从而在减少内存占用的情况下进行微调。

## 相对动作 (Relative Actions)

默认情况下，π₀ 预测绝对动作。您可以启用**相对动作**，使模型预测相对于当前机器人状态的偏移量。这可以提高某些设置下的训练稳定性。

要使用相对动作，请首先通过 CLI 在相对空间中重新计算数据集统计量

```
lerobot-edit-dataset \
    --repo_id your_dataset \
    --operation.type recompute_stats \
    --operation.relative_action true \
    --operation.chunk_size 50 \
    --operation.relative_exclude_joints "['gripper']" \
    --push_to_hub true
```

或者在 Python 中等效执行

```
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.dataset_tools import recompute_stats

dataset = LeRobotDataset("your_dataset")
recompute_stats(dataset, relative_action=True, chunk_size=50, relative_exclude_joints=["gripper"])
dataset.push_to_hub()
```

`chunk_size` 应与策略的 `chunk_size` 一致（π₀ 默认为 50）。`relative_exclude_joints` 列出应保持在绝对空间的关节名称（例如夹爪指令）。使用 `--push_to_hub true` 将更新后的统计量上传到 Hub。

然后启用相对动作进行训练

```
lerobot-train \
    --dataset.repo_id=your_dataset \
    --policy.type=pi0 \
    --policy.use_relative_actions=true \
    --policy.relative_exclude_joints='["gripper"]' \
    ...
```

## 许可证

此模型遵循 \*\*Apache 2.0 许可证\*\*，与原始的 [OpenPI 仓库](https://github.com/Physical-Intelligence/openpi)一致。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/pi0.mdx)
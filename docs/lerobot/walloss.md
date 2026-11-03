# 来源

https://hugging-face.cn/docs/lerobot/walloss

# WALL-OSS

WALL-OSS 是一个由 [XSquare Robot](https://x2robot.com/en/research/68bc2cde8497d7f238dde690) 团队在 2025 年提出的具身智能开源基座模型。其 LeRobot 实现版本改编自他们的开源 [WallX](https://github.com/X-Square-Robot/wall-x) 仓库。

X Square Robot 的 WALL-OSS 现已集成到 Hugging Face 的 LeRobot 生态系统中。这是 LeRobot 和 X Square Robot 团队之间一次令人兴奋的协作项目。您现在可以直接通过 LeRobot 对 WALL-OSS 进行后训练（post-train）、评估和部署。通过此次集成，我们的目标是让开源机器人社区能够更轻松地定制和部署 WALL-OSS 基座模型。阅读并探索 WALL-OSS 的 [论文](https://arxiv.org/pdf/2509.11766)和[代码](https://github.com/X-Square-Robot/wall-x)。

## 模型概述

WALL-OSS 团队正在构建这个具身基座模型，旨在捕捉和压缩世界上最宝贵的数据：连续且高保真的物理交互流。通过在模型的决策与身体的实际体验之间建立直接的反馈循环，从而实现真正可泛化智能的涌现——这种智能不仅理解世界如何运作，而且懂得如何在其中高效地行动。

![An overview of WALL-OSS](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/walloss-lerobot-paper.png)

在技术上，WALL-OSS 引入了一种紧耦合的多模态架构（紧耦合 MoE 结构），该架构集成了离散和连续的动作建模策略。通过两阶段训练流水线（启发 → 集成），模型逐渐统一了语义推理与高频动作生成。其核心创新包括：

* **具身感知增强的多模态预训练**：在统一的视觉-语言-动作（VLA）数据上进行大规模训练，以增强空间、因果和操纵能力的理解。
* **统一跨层思维链 (Uni-CoT)**：一个单一的可微框架，将高层指令推理、子任务分解和细粒度动作合成相统一，形成了从“理解”到“执行”的连续链条。
* **混合专家 (MoE) 动作头**：根据任务阶段动态激活专家，并在离散或连续空间中对动作进行建模，以维持稳定的 VLM 先验。
* **两阶段训练范式**:
  + **启发阶段 (Inspiration stage)**：注入离散动作先验，以增强空间理解和语义-动作对齐。
  + **集成阶段 (Integration stage)**：使用流匹配（flow matching）实现高频连续控制。

## 安装要求

1. 请遵循我们的[安装指南](installation.md)来安装 LeRobot。
2. 运行以下命令安装 WallX 依赖项：

   ```
   pip install -e ".[wallx]"
   ```

## 用法

要在 LeRobot 中使用 WallX，请将策略类型指定为：

```
policy.type=wall_x
```

## 训练

对于训练 WallX，您可以使用带有相应配置的标准 LeRobot 训练脚本：

```
lerobot-train \
    --dataset.repo_id=your_dataset \
    --policy.type=wall_x \
    --output_dir=./outputs/wallx_training \
    --job_name=wallx_training \
    --policy.repo_id=your_repo_id \
    --policy.pretrained_name_or_path=x-square-robot/wall-oss-flow \
    --policy.prediction_mode=diffusion \
    --policy.attn_implementation=eager \
    --steps=3000 \
    --policy.device=cuda \
    --batch_size=32
```

### 训练参数

| 参数 | 描述 |
| --- | --- |
| `--dataset.repo_id` | 训练数据集的 Hugging Face Hub 仓库 ID（例如：`lerobot/aloha_sim_insertion_human`） |
| `--policy.type` | 指定使用 WallX 策略架构 |
| `--output_dir` | 保存训练检查点和日志的本地目录 |
| `--job_name` | 此次训练运行的名称标识符（用于日志记录/跟踪） |
| `--policy.repo_id` | 训练后的模型将推送到的 Hugging Face Hub 仓库 ID |
| `--policy.pretrained_path` | 用于初始化的预训练 WallX 权重路径（官方 WALL-OSS 检查点） |
| `--policy.prediction_mode` | 动作预测策略：`diffusion` 或 `fast` - `diffusion` 使用迭代去噪生成动作，`fast` 则使用下一个 token 预测 |
| `--policy.attn_implementation` | 注意力机制实现后端 - `eager` 使用标准 PyTorch 注意力（其他选项包括 `flash_attention_2` 或 `sdpa`） |
| `--steps` | 运行的总训练步数 |
| `--policy.device` | 训练设备（`cuda` 为 GPU，`cpu` 为 CPU） |
| `--batch_size` | 每个训练批次的样本数量 |

## 许可证

本模型遵循 **Apache 2.0 许可证**，与原 [WallX 仓库](https://github.com/X-Square-Robot/wall-x)一致。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/walloss.mdx)
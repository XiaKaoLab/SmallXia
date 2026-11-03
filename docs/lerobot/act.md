# 来源

https://hugging-face.cn/docs/lerobot/act

# ACT (Action Chunking with Transformers)

ACT 是一种**轻量且高效的模仿学习策略**，特别适用于精细的操作任务。由于其训练时间快、计算需求低且性能强劲，它是我们**建议您在开始使用** LeRobot 时首先尝试的模型。

*观看 LeRobot 团队的这个教程来了解 ACT 的工作原理：[LeRobot ACT 教程](https://www.youtube.com/watch?v=ft73x0LfGpM)*

## 模型概述

Action Chunking with Transformers (ACT) 是在 Zhao 等人的论文 [Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware](https://arxiv.org/abs/2304.13705) 中提出的。该策略旨在利用经济的硬件和极少的演示数据来实现精确且具有丰富接触的操作任务。

### 为什么 ACT 非常适合初学者

ACT 之所以是一个极佳的起点，原因有以下几点：

* **快速训练**：在单个 GPU 上仅需几个小时即可完成训练
* **轻量级**：参数量仅约 80M，使其高效且易于操作
* **数据高效**：通常仅需 50 次演示即可实现较高的成功率

### 架构

ACT 使用基于 Transformer 的架构，包含三个主要组件：

1. **视觉骨干网络 (Vision Backbone)**：使用 ResNet-18 处理来自多个摄像机视角的图像
2. **Transformer 编码器**：综合来自摄像机特征、关节位置和学习到的潜变量的信息
3. **Transformer 解码器**：使用交叉注意力机制 (cross-attention) 生成连贯的动作序列

该策略的输入为：

* 多张 RGB 图像（例如：来自腕部摄像机、前方/上方摄像机）
* 机器人当前的关节位置
* 一个潜风格变量 `z`（在训练期间学习，在推理期间设为零）

并输出一段包含 `k` 个未来动作序列的块 (chunk)。

## 安装要求

1. 请遵循我们的[安装指南](installation.md)来安装 LeRobot。
2. ACT 已包含在 LeRobot 基础安装中，因此不需要额外的依赖项！

## 训练 ACT

ACT 与标准的 LeRobot 训练流水线无缝协作。以下是在您的数据集上训练 ACT 的完整示例：

```
lerobot-train \
  --dataset.repo_id=${HF_USER}/your_dataset \
  --policy.type=act \
  --output_dir=outputs/train/act_your_dataset \
  --job_name=act_your_dataset \
  --policy.device=cuda \
  --wandb.enable=true \
  --policy.repo_id=${HF_USER}/act_policy
```

### 训练技巧

1. **从默认设置开始**：ACT 的默认超参数适用于大多数任务
2. **训练时长**：在单个 GPU 上完成 100k 个训练步数预计需要几个小时
3. **批大小 (Batch size)**：从批大小 8 开始，并根据您的 GPU 显存进行调整

### 使用 Google Colab 训练

如果您的本地计算机没有强大的 GPU，您可以按照 [ACT 训练笔记本](notebooks.md#training-act) 使用 Google Colab 来训练您的模型。

## 评估 ACT

训练完成后，您可以使用 `lerobot-record` 命令配合训练好的策略来评估您的 ACT 策略。这将运行推理并记录评估回合。

```
lerobot-record \
  --robot.type=so100_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=my_robot \
  --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
  --display_data=true \
  --dataset.repo_id=${HF_USER}/eval_act_your_dataset \
  --dataset.num_episodes=10 \
  --dataset.single_task="Your task description" \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2 \
  # --dataset.vcodec=auto \
  --policy.path=${HF_USER}/act_policy
```

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/act.mdx)
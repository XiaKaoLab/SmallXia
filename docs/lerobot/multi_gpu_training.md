# 来源

https://hugging-face.cn/docs/lerobot/multi_gpu_training

# 多 GPU 训练

本指南将向您展示如何使用 [Hugging Face Accelerate](https://hugging-face.cn/docs/accelerate) 在多个 GPU 上训练策略。

## 安装

首先，请确保您已安装 accelerate

```
pip install accelerate
```

## 使用多个 GPU 进行训练

您可以通过两种方式启动训练

### 方案 1：不使用配置文件（直接指定参数）

您可以在命令中直接指定所有参数，而无需运行 `accelerate config`

```
accelerate launch \
  --multi_gpu \
  --num_processes=2 \
  $(which lerobot-train) \
  --dataset.repo_id=${HF_USER}/my_dataset \
  --policy.type=act \
  --policy.repo_id=${HF_USER}/my_trained_policy \
  --output_dir=outputs/train/act_multi_gpu \
  --job_name=act_multi_gpu \
  --wandb.enable=true
```

**关键的 accelerate 参数**

* `--multi_gpu`: 启用多 GPU 训练
* `--num_processes=2`: 使用的 GPU 数量
* `--mixed_precision=fp16`: 使用 fp16 混合精度（如果支持，也可以使用 `bf16`）

### 方案 2：使用 accelerate config

如果您希望保存配置，可以通过运行以下命令为您的硬件设置配置 accelerate

```
accelerate config
```

此交互式设置将询问您关于训练环境的问题（GPU 数量、混合精度设置等），并将配置保存以供将来使用。对于单机上的简单多 GPU 设置，您可以使用以下推荐设置

* 计算环境 (Compute environment)：本机器 (This machine)
* 机器数量 (Number of machines)：1
* 进程数量 (Number of processes)：(您想要使用的 GPU 数量)
* 要使用的 GPU ID (GPU ids to use)：(留空以使用所有 GPU)
* 混合精度 (Mixed precision)：fp16 或 bf16 (推荐，可加快训练速度)

然后使用以下命令启动训练

```
accelerate launch $(which lerobot-train) \
  --dataset.repo_id=${HF_USER}/my_dataset \
  --policy.type=act \
  --policy.repo_id=${HF_USER}/my_trained_policy \
  --output_dir=outputs/train/act_multi_gpu \
  --job_name=act_multi_gpu \
  --wandb.enable=true
```

## 工作原理

当您使用 accelerate 启动训练时

1. **自动检测**：LeRobot 会自动检测其是否在 accelerate 环境下运行
2. **数据分布**：您的 batch 会自动分配到各个 GPU 上
3. **梯度同步**：在反向传播期间，梯度会在各个 GPU 之间进行同步
4. **单进程日志**：只有主进程会记录日志到 wandb 并保存检查点

## 学习率和训练步数的缩放

**重要提示：** LeRobot **不会**根据 GPU 的数量自动缩放学习率或训练步数。这让您可以完全控制训练超参数。

### 为什么不进行自动缩放？

许多分布式训练框架会自动根据 GPU 数量缩放学习率（例如，`lr = base_lr × num_gpus`）。然而，LeRobot 会严格保持您指定的学习率。

### 何时以及如何缩放

如果您希望在使用多个 GPU 时缩放超参数，您应该手动执行此操作

**学习率缩放**

```
# Example: 2 GPUs with linear LR scaling
# Base LR: 1e-4, with 2 GPUs -> 2e-4
accelerate launch --num_processes=2 $(which lerobot-train) \
  --optimizer.lr=2e-4 \
  --dataset.repo_id=lerobot/pusht \
  --policy=act
```

**训练步数缩放**

由于有效 batch 大小 `bs` 随着 GPU 数量的增加而增加（batch\_size × num\_gpus），您可能希望按比例减少训练步数

```
# Example: 2 GPUs with effective batch size 2x larger
# Original: batch_size=8, steps=100000
# With 2 GPUs: batch_size=8 (16 in total), steps=50000
accelerate launch --num_processes=2 $(which lerobot-train) \
  --batch_size=8 \
  --steps=50000 \
  --dataset.repo_id=lerobot/pusht \
  --policy=act
```

## 注意事项

* `lerobot-train` 中的 `--policy.use_amp` 标志仅在 **不** 使用 accelerate 运行时生效。当使用 accelerate 时，混合精度由 accelerate 的配置控制。
* 训练日志、检查点和 Hub 上传仅由主进程执行，以避免冲突。非主进程的控制台日志被禁用，以防止重复输出。
* 有效 batch 大小为 `batch_size × num_gpus`。如果您使用 4 个 GPU 且设置 `--batch_size=8`，则有效 batch 大小为 32。
* 学习率调度在多个进程之间得到了正确处理——LeRobot 设置 `step_scheduler_with_optimizer=False`，以防止 accelerate 根据进程数量调整调度步数。
* 在保存或推送模型时，LeRobot 会自动将模型从 accelerate 的分布式包装器中解包，以确保兼容性。
* WandB 集成自动仅在主进程上初始化，防止创建多个运行记录。

有关更高级的配置和故障排除，请参阅 [Accelerate 文档](https://hugging-face.cn/docs/accelerate)。如果您想了解更多关于如何在大量 GPU 上进行训练的信息，请查看这个很棒的指南：[Ultrascale Playbook](https://hugging-face.cn/spaces/nanotron/ultrascale-playbook)。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/multi_gpu_training.mdx)
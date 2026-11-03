# 来源

https://hugging-face.cn/docs/lerobot/libero

# LIBERO

LIBERO 是一个旨在研究**终身机器人学习**的基准测试——其核心理念是机器人需要随着时间的推移不断学习并适应用户，而不仅仅是进行一次性的预训练。它提供了一套标准化的操作任务，重点在于**知识迁移**：机器人如何将其已学到的知识应用到新情境中。通过对 LIBERO 进行评估，可以公平地比较不同的算法，研究人员也能够在彼此的工作基础上进行开发。

* 论文：[Benchmarking Knowledge Transfer for Lifelong Robot Learning（终身机器人学习的知识迁移基准测试）](https://arxiv.org/abs/2306.03310)
* GitHub：[Lifelong-Robot-Learning/LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO)
* 项目网站：[libero-project.github.io](https://libero-project.github.io)

![An overview of the LIBERO benchmark](https://libero-project.github.io/assets/img/libero/fig1.png)

## 可用任务

LIBERO 包含**五个任务套件**，涵盖**130个任务**，范围从简单的物体操作到复杂的多步骤场景。

| 套件 | CLI 名称 | 任务 | 描述 |
| --- | --- | --- | --- |
| LIBERO-Spatial | `libero_spatial` | 10 | 需要空间关系推理的任务 |
| LIBERO-Object | `libero_object` | 10 | 以操作不同物体为核心的任务 |
| LIBERO-Goal | `libero_goal` | 10 | 具有变化目标的目标条件任务 |
| LIBERO-90 | `libero_90` | 90 | 来自 LIBERO-100 集合的短时程任务 |
| LIBERO-Long | `libero_10` | 10 | 来自 LIBERO-100 集合的长时程任务 |

## 安装

按照 LeRobot 的安装说明操作后

```
pip install -e ".[libero]"
```

> LIBERO 需要 Linux (`sys\_platform == 'linux'`)。LeRobot 使用 MuJoCo 进行模拟——在训练或评估前请设置渲染后端。
>
> ```
> export MUJOCO_GL=egl  # for headless servers (HPC, cloud)
> ```

## 评估

### 默认评估（推荐）

在四个标准套件中进行评估（每个任务 10 个片段）

```
lerobot-eval \
  --policy.path="your-policy-id" \
  --env.type=libero \
  --env.task=libero_spatial,libero_object,libero_goal,libero_10 \
  --eval.batch_size=1 \
  --eval.n_episodes=10 \
  --env.max_parallel_tasks=1
```

### 单套件评估

在单个 LIBERO 套件上进行评估

```
lerobot-eval \
  --policy.path="your-policy-id" \
  --env.type=libero \
  --env.task=libero_object \
  --eval.batch_size=2 \
  --eval.n_episodes=3
```

* `--env.task` 选择套件（`libero_object`, `libero_spatial` 等）。
* `--env.task_ids` 限制为特定的任务索引（`[0]`, `[1,2,3]` 等）。忽略此项则运行套件中的所有任务。
* `--eval.batch_size` 控制并行运行的环境数量。
* `--eval.n_episodes` 设置每个任务运行的片段数量。

### 多套件评估

通过传入逗号分隔的列表，同时对多个套件进行策略基准测试。

```
lerobot-eval \
  --policy.path="your-policy-id" \
  --env.type=libero \
  --env.task=libero_object,libero_spatial \
  --eval.batch_size=1 \
  --eval.n_episodes=2
```

### 控制模式

LIBERO 支持两种控制模式——`relative`（相对，默认）和 `absolute`（绝对）。不同的 VLA 检查点是使用不同的动作参数化进行训练的，因此请确保模式与您的策略相匹配。

```
--env.control_mode=relative   # or "absolute"
```

### 策略输入和输出

**观察**

* `observation.state` — 8 维本体感受特征（末端执行器位置、轴角方向、夹爪位置）。
* `observation.images.image` — 主摄像机视图（`agentview_image`），HWC uint8 格式。
* `observation.images.image2` — 腕部摄像机视图（`robot0_eye_in_hand_image`），HWC uint8 格式。

> LeRobot 强制要求视觉特征使用 `.images.*` 前缀。请确保您的策略配置 `input_features` 使用相同的命名键，并且数据集元数据键遵循此约定。如果您的数据包含不同的键，您必须重命名观察数据以符合策略的预期，因为命名键已编码在归一化统计层中。

**动作**

* `Box(-1, 1, shape=(7,))` 中的连续控制——6D 末端执行器增量 + 1D 夹爪。

### 推荐评估片段数

为了进行可重现的基准测试，请在所有四个标准套件（Spatial, Object, Goal, Long）中使用**每个任务 10 个片段**。总计 400 个片段，这与已发表结果所使用的方案一致。

## 训练

### 数据集

我们提供了一个与 LeRobot 完全兼容的预处理 LIBERO 数据集：

* [HuggingFaceVLA/libero](https://hugging-face.cn/datasets/HuggingFaceVLA/libero)

作为参考，Physical Intelligence 发布的原版数据集：

* [physical-intelligence/libero](https://hugging-face.cn/datasets/physical-intelligence/libero)

### 训练命令示例

```
lerobot-train \
  --policy.type=smolvla \
  --policy.repo_id=${HF_USER}/libero-test \
  --policy.load_vlm_weights=true \
  --dataset.repo_id=HuggingFaceVLA/libero \
  --env.type=libero \
  --env.task=libero_10 \
  --output_dir=./outputs/ \
  --steps=100000 \
  --batch_size=4 \
  --eval.batch_size=1 \
  --eval.n_episodes=1 \
  --eval_freq=1000
```

## 复现已发表结果

我们复现了 Pi0.5 在 LIBERO 基准测试上的结果。我们使用 Physical Intelligence 的 LIBERO 基础模型 (`pi05_libero`)，在 8 个 H100 GPU 上使用 [HuggingFace LIBERO 数据集](https://hugging-face.cn/datasets/HuggingFaceVLA/libero)，以 bfloat16 精度、256 的批处理大小进行了额外的 6k 步微调。

微调后的模型：[lerobot/pi05\_libero\_finetuned](https://hugging-face.cn/lerobot/pi05_libero_finetuned)

### 评估命令

```
lerobot-eval \
  --output_dir=./eval_logs/ \
  --env.type=libero \
  --env.task=libero_spatial,libero_object,libero_goal,libero_10 \
  --eval.batch_size=1 \
  --eval.n_episodes=10 \
  --policy.path=pi05_libero_finetuned \
  --policy.n_action_steps=10 \
  --env.max_parallel_tasks=1
```

我们将 `n_action_steps=10`，与原始 OpenPI 实现保持一致。

### 结果

| 模型 | LIBERO Spatial | LIBERO Object | LIBERO Goal | LIBERO 10 | 平均分 |
| --- | --- | --- | --- | --- | --- |
| **Pi0.5 (LeRobot)** | 97.0 | 99.0 | 98.0 | 96.0 | **97.5** |

这些结果与 Physical Intelligence 报告的[原始结果](https://github.com/Physical-Intelligence/openpi/tree/main/examples/libero#results)一致。

| 模型 | LIBERO Spatial | LIBERO Object | LIBERO Goal | LIBERO 10 | 平均分 |
| --- | --- | --- | --- | --- | --- |
| **Pi0.5 (OpenPI)** | 98.8 | 98.2 | 98.0 | 92.4 | **96.85** |

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/libero.mdx)
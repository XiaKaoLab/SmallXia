# 来源

https://hugging-face.cn/docs/lerobot/metaworld

# Meta-World

Meta-World 是一个用于连续控制机器人操纵的**多任务和元强化学习**开源仿真基准。它整合了使用日常物品和通用桌面 Sawyer 机械臂的 50 个多样化操纵任务，提供了一个标准化的平台，用于测试算法是否能够学习许多不同的任务并快速泛化到新任务中。

* 论文： [Meta-World: A Benchmark and Evaluation for Multi-Task and Meta Reinforcement Learning](https://arxiv.org/abs/1910.10897)
* GitHub： [Farama-Foundation/Metaworld](https://github.com/Farama-Foundation/Metaworld)
* 项目网站： [metaworld.farama.org](https://metaworld.farama.org)

![MetaWorld MT10 demo](https://meta-world.github.io/figures/ml45.gif)

## 可用任务

Meta-World 提供了 50 个按难度分组的任务。在 LeRobot 中，您可以对单个任务、难度组或完整的 MT50 套件进行评估

| 分组 | CLI 名称 | 任务 | 描述 |
| --- | --- | --- | --- |
| 简单 (Easy) | `easy` | 28 | 具有简单动力学和单步目标的任务 |
| 中型 | `medium` | 11 | 需要多步推理的任务 |
| 困难 (Hard) | `hard` | 6 | 具有复杂接触和精确操纵的任务 |
| 极难 (Very Hard) | `very_hard` | 5 | 该套件中最具挑战性的任务 |
| MT50 (全部) | 逗号分隔列表 | 50 | 全部 50 个任务 —— 最具挑战性的多任务设置 |

您也可以直接传递单个任务名称（例如：`assembly-v3`, `dial-turn-v3`）。

我们在 HF Hub 上提供了一个适用于 LeRobot 的 Meta-World MT50 数据集：[lerobot/metaworld\_mt50](https://hugging-face.cn/datasets/lerobot/metaworld_mt50)。该数据集专为 MT50 评估而格式化，使用全部 50 个任务，且为了保持一致性，物体/目标位置固定，并使用 one-hot 任务向量。

## 安装

在按照 LeRobot 安装指南操作后

```
pip install -e ".[metaworld]"
```

> 如果您在运行 Meta-World 环境时遇到 `AssertionError: ['human', 'rgb\_array', 'depth\_array']`，这是因为 Meta-World 与您的 Gymnasium 版本不匹配。可以通过以下方式修复：
>
> ```
> pip install "gymnasium==1.1.0"
> ```

## 评估

### 默认评估（推荐）

在 medium 难度分片上进行评估（覆盖范围和计算开销之间的良好平衡）

```
lerobot-eval \
  --policy.path="your-policy-id" \
  --env.type=metaworld \
  --env.task=medium \
  --eval.batch_size=1 \
  --eval.n_episodes=10
```

### 单任务评估

对特定任务进行评估

```
lerobot-eval \
  --policy.path="your-policy-id" \
  --env.type=metaworld \
  --env.task=assembly-v3 \
  --eval.batch_size=1 \
  --eval.n_episodes=10
```

### 多任务评估

在多个任务或难度组之间进行评估

```
lerobot-eval \
  --policy.path="your-policy-id" \
  --env.type=metaworld \
  --env.task=assembly-v3,dial-turn-v3,handle-press-side-v3 \
  --eval.batch_size=1 \
  --eval.n_episodes=10
```

* `--env.task` 接受显式的任务列表（逗号分隔）或难度组（例如：`easy`, `medium`, `hard`, `very_hard`）。
* `--eval.batch_size` 控制并行运行的环境数量。
* `--eval.n_episodes` 设置每个任务运行的回合数。

### 策略输入和输出

**观察**

* `observation.image` — 单摄像头视角 (`corner2`), 480x480 HWC uint8
* `observation.state` — 4 维本体感受状态 (末端执行器位置 + 夹持器)

**动作**

* 连续控制范围 `Box(-1, 1, shape=(4,))` — 3D 末端执行器增量 + 1D 夹持器

### 推荐评估回合数

为了确保基准测试的可重复性，请使用 **每个任务 10 个回合**。对于完整的 MT50 套件，这将总共产生 500 个回合。如果您关注泛化能力，请在完整的 MT50 上运行 —— 它被刻意设计得具有挑战性，比几个狭窄的任务更能揭示模型的优缺点。

## 训练

### 训练命令示例

在 Meta-World 任务子集上训练 SmolVLA 策略

```
lerobot-train \
  --policy.type=smolvla \
  --policy.repo_id=${HF_USER}/metaworld-test \
  --policy.load_vlm_weights=true \
  --dataset.repo_id=lerobot/metaworld_mt50 \
  --env.type=metaworld \
  --env.task=assembly-v3,dial-turn-v3,handle-press-side-v3 \
  --output_dir=./outputs/ \
  --steps=100000 \
  --batch_size=4 \
  --eval.batch_size=1 \
  --eval.n_episodes=1 \
  --eval_freq=1000
```

## 实用技巧

* 在多任务训练中（遵循 MT10/MT50 约定）使用 one-hot 任务条件，以便策略具有明确的任务上下文。
* 在编写后处理或日志记录时，请检查数据集的任务描述和 `info["is_success"]` 键，以确保您的成功指标与基准测试一致。
* 根据您的计算预算调整 `batch_size`, `steps` 和 `eval_freq`。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/metaworld.mdx)
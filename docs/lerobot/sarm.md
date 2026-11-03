# 来源

https://hugging-face.cn/docs/lerobot/sarm

# SARM: 阶段感知奖励建模

SARM（阶段感知奖励建模）是一种用于长程机器人操作任务的基于视频的奖励建模框架。本指南涵盖了如何训练 SARM 奖励模型，以及如何选择性地将其与奖励对齐行为克隆（RA-BC）结合使用。

**论文**: [SARM: Stage-Aware Reward Modeling for Long Horizon Robot Manipulation (用于长程机器人操作的阶段感知奖励建模)](https://arxiv.org/abs/2509.25358)

![An overview of SARM](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/lerobot-sarm.png)

## 为什么需要奖励模型？

标准的行为克隆将所有演示帧同等对待，但现实世界的机器人数据集通常很混乱。它们包含迟疑、修正以及质量参差不齐的轨迹。奖励模型通过从演示中学习一种可泛化的**任务进度**概念来解决这个问题：给定视频帧和任务描述，它们预测机器人距离完成任务有多近（0→1）。这种学习到的“进度信号”可以以多种方式使用，两个有前景的应用是：（1）**加权模仿学习**（RA-BC），即在策略训练期间，高进度帧会被赋予更高的权重；以及（2）**强化学习**，即奖励模型为在线或离线策略改进提供稠密奖励。

## 概述

SARM 具有以下特点

1. **阶段感知架构**：联合预测高级任务阶段以及每个阶段内的细粒度进度
2. **子任务标注**：使用自然语言子任务标注来推导一致的进度标签
3. **时间比例**：计算每个子任务的数据集级先验（α̅\_k），以标准化不同长度演示中的进度

SARM 针对每一帧训练一个紧凑的 **stage+tau** 目标

* **stage**：整数阶段索引 `k ∈ {0, ..., K-1}`
* **τ (tau)**：阶段内进度 `τ ∈ [0, 1]`
* **目标编码**：`y = k + τ`（这是数据集处理器生成的内容）

在推理时（以及在后续的 RA-BC 中），SARM 使用数据集级的**时间比例** `α̅_k`（存储在 `meta/temporal_proportions_*.json` 中）将原始的 `k + τ` 值转换为 `[0, 1]` 范围内的**标准化进度**。

这符合论文中的**公式 (2)**

```
progress_t = P_{k-1} + α̅_k × τ_t
```

其中：

* `τ_t = (t - s_k) / (e_k - s_k)` 是子任务内的时间标准化值
* `P_{k-1}` 是累积先验（之前子任务比例之和）
* `α̅_k` 是子任务 k 的时间比例

这确保了相同的任务状态映射到一致的进度值，即使在不同长度的演示中也是如此。

## 输入和目标（新代码期望的内容）

SARM 通过其处理器（`src/lerobot/policies/sarm/processor_sarm.py`）进行训练，该处理器

* **使用 CLIP (ViT-B/32) 将** 图像和任务文本编码为 `video_features` 和 `text_features`
* **将机器人状态填充/截断** 为 `state_features`（上限为 `max_state_dim`）
* **使用 stage+tau 编码** `y = k + τ` 构建 `sparse_targets`（以及 `dense_only`/`dual` 中的 `dense_targets`）
* **使用每个样本的** `lengths` 张量遮蔽重放帧（重放是一种训练时的数据增强）

至少每个训练样本需要

* `task`（字符串）：任务描述
* 来自数据集的 `policy.image_key` 图像和 `policy.state_key` 状态

---

## 标注模式

您可以从 **3 种标注模式** 中选择，它们决定了如何计算进度标签

| 模式 | 所需标注 | 头 | 用例 |
| --- | --- | --- | --- |
| `single_stage` | 无 | 仅稀疏 | 简单任务，快速实验，无需 VLM |
| `dense_only` | 稠密 (VLM) | 双重（稀疏自动生成） | 无需定义高级阶段即可进行详细的子任务跟踪 |
| `dual` | 稀疏 + 稠密 (VLM) | 双重 | 完整的 SARM 论文设置，兼具两种粒度 |

### 模式详情

single\_stage

dense\_only

dual

**无需标注。** 整个片段被视为一个名为 `"task"` 的单一阶段，进度在片段持续时间内从 0 线性增加到 1。

* **稀疏头**：1 个阶段（“task”），线性进度
* **稠密头**：未使用
* **最适合**：简单任务、快速实验，或无法进行 VLM 标注时

## 设置您的环境

1. 请遵循我们的[安装指南](installation.md)来安装 LeRobot。
2. 通过运行以下命令安装 SARM 依赖项

```
pip install -e ".[sarm]"
```

工作流程

```
1. Train SARM → 2. Visualize predictions → 3. (Optional) Train policy with RA-BC
```

---

## 第一步：子任务标注

single\_stage

dense\_only

dual

**无需标注！** 完全跳过此步骤。模型将使用片段的任务描述并自动计算线性进度。

### 标注参数

| 参数 | 描述 |
| --- | --- |
| `--repo-id` | HuggingFace 数据集仓库 ID |
| `--sparse-subtasks` | 高级子任务名称的逗号分隔列表 |
| `--dense-subtasks` | 细粒度子任务名称的逗号分隔列表 |
| `--dense-only` | 仅生成稠密标注（自动创建稀疏“任务”阶段） |
| `--video-key` | 要使用的相机/视频键（例如：`observation.images.top`） |
| `--num-workers` | 并行 GPU 工作线程数量（默认：1） |
| `--episodes` | 要标注的特定片段索引（默认：全部） |
| `--skip-existing` | 跳过已有标注的片段 |
| `--model` | VLM 模型（默认：`Qwen/Qwen3-VL-30B-A3B-Instruct`） |
| `--num-visualizations` | 标注后要可视化的片段数量（默认：5，设置为 0 跳过） |

> **注意**：标注完成后，默认会自动可视化 5 个片段。使用 `--num-visualizations 0` 跳过此步骤。

---

## 第二步：验证标注

single\_stage

dense\_only

dual

**无需验证！** 跳过此步骤。

这会生成可视化图，显示带有叠加子任务边界的视频帧和子任务时间线。

### 可视化参数

| 参数 | 描述 |
| --- | --- |
| `--visualize-only` | 仅可视化现有标注（不生成） |
| `--num-visualizations` | 要可视化的片段数量（默认：5） |
| `--visualize-type` | 要可视化的标注类型：`sparse`、`dense` 或 `both` |

**提示**：如果标注不准确，请调整您的子任务描述使其更具体，然后重新运行。

---

## 第三步：训练 SARM

single\_stage

dense\_only

dual

在**无标注**的情况下训练 - 使用从 0 到 1 的线性进度

```
lerobot-train \
  --dataset.repo_id=your-username/your-dataset \
  --policy.type=sarm \
  --policy.annotation_mode=single_stage \
  --policy.image_key=observation.images.base \
  --output_dir=outputs/train/sarm_single \
  --batch_size=32 \
  --steps=5000 \
  --wandb.enable=true \
  --wandb.project=sarm \
  --policy.repo_id=your-username/your-model-name
```

### 多 GPU 训练

添加 `accelerate launch --multi_gpu --num_processes=4` 以使用多个 GPU 进行训练。

### 训练参数

| 参数 | 描述 | 默认 |
| --- | --- | --- |
| `--policy.annotation_mode` | `single_stage`、`dense_only` 或 `dual` | `single_stage` |
| `--policy.image_key` | 图像的相机键 | `observation.images.top` |
| `--policy.state_key` | 关节状态的键 | `observation.state` |
| `--policy.n_obs_steps` | 观测历史步骤（总观测帧数 = `n_obs_steps + 1`） | `8` |
| `--policy.frame_gap` | 采样观测之间的间隔（以帧为单位）（30 fps 时：30 ≈ 1s） | `30` |

---

## 第四步：可视化预测

使用带有 `--visualize-only` 的 `compute_rabc_weights.py` 来可视化模型预测（如果可用，还有标注导出的目标），而不写入 parquet 文件。

single\_stage

dense\_only

dual

```
python src/lerobot/policies/sarm/compute_rabc_weights.py \
  --dataset-repo-id your-username/your-dataset \
  --reward-model-path your-username/sarm-model \
  --visualize-only \
  --num-visualizations 5 \
  --head-mode sparse \
  --output-dir ./sarm_viz
```

可视化显示

* **进度图**：预测进度（以及在可用且 `--stride 1` 时，可选的标注导出的“GT”）
* **阶段概率**：预测阶段概率的堆叠面积图
* **示例帧**：片段中的关键帧，带有进度/阶段标签

### 可视化参数

| 参数 | 描述 |
| --- | --- |
| `--visualize-only` | 仅可视化预测（不进行 RABC 计算） |
| `--num-visualizations` | 要可视化的片段数量（默认：5） |
| `--head-mode` | 要使用的 SARM 头：`sparse`、`dense` 或 `both` |
| `--stride` | 每 N 帧计算一次，其余帧进行插值（默认：1） |

---

## 第五步（可选）：使用 RA-BC 训练策略

奖励对齐行为克隆（RA-BC）使用经过训练的 SARM 模型，根据预测的进度提升来加权训练样本。这需要两个步骤

1. **预计算进度值**：使用经过训练的 SARM 模型计算所有帧的进度值
2. **训练策略**：使用预计算的值进行 RA-BC 加权策略训练

### RA-BC 如何工作

对于每个训练样本，RA-BC 计算进度差

```
r_i = φ(o_{t+Δ}) - φ(o_t)
```

其中 `φ` 是 SARM 进度预测，`Δ` 是策略的 `chunk_size`。具有正进度的样本（良好的演示）获得更高的权重，而具有负进度或零进度的样本则权重降低。

加权遵循论文中的**等式 8-9**

* **软权重**：`w̃_i = clip((r_i − (μ − 2σ)) / (4σ + ε), 0, 1)`
* **最终权重**：`w_i = 𝟙{r_i > κ} + 𝟙{0 ≤ r_i ≤ κ} × w̃_i`

### 第五步 a：计算 SARM 进度值

首先，在数据集的所有帧上运行 SARM 模型以计算进度值

```
python src/lerobot/policies/sarm/compute_rabc_weights.py \
  --dataset-repo-id your-username/your-dataset \
  --reward-model-path your-username/sarm-model \
  --head-mode sparse \
  --num-visualizations 5 \
  --push-to-hub
```

此脚本

* 处理所有帧并计算进度值
* 将进度值保存到磁盘上数据集旁边的 parquet 文件中（默认为 `<dataset_root>/sarm_progress.parquet`）
* 生成前 N 个片段的可视化图（默认：5）

**参数**

| 参数 | 描述 | 默认 |
| --- | --- | --- |
| `--reward-model-path` | 指向经过训练的 SARM 模型的路径 | （必需） |
| `--head-mode` | 要使用的 SARM 头：`sparse`、`dense` 或 `both` | `sparse` |
| `--device` | 推理设备 | `cuda` |
| `--visualize-only` | 仅可视化预测（不进行 RA-BC 计算） | `false` |
| `--num-visualizations` | 要可视化的片段数量（默认：5，设置为 0 跳过） | `5` |

**输出格式** (`sarm_progress.parquet`)

| 列 | 描述 |
| --- | --- |
| `索引` | 数据集中的全局帧索引 |
| `episode_index` | 片段编号 |
| `frame_index` | 片段内的局部帧索引 |
| `progress_sparse` | 稀疏头进度值 [0, 1] |
| `progress_dense` | 稠密头进度值 [0, 1]（如果已计算） |

### 第五步 b：使用 RA-BC 训练策略

一旦有了进度文件，就可以使用 RA-BC 加权训练您的策略。进度文件会从数据集路径（`sarm_progress.parquet`）中自动检测。目前 PI0、PI0.5 和 SmolVLA 支持 RA-BC

```
lerobot-train \
  --dataset.repo_id=your-username/your-dataset \
  --policy.type=pi0 \
  --use_rabc=true \
  --rabc_head_mode=sparse \
  --rabc_kappa=0.01 \
  --output_dir=outputs/train/policy_rabc \
  --batch_size=32 \
  --steps=40000
```

训练脚本会自动

* 从 parquet 文件加载预计算的进度值
* 使用策略的 `chunk_size` 来计算进度差 (Δ)
* 根据进度提升计算样本权重
* 在训练期间应用加权损失

**RA-BC 参数**

| 参数 | 描述 | 默认 |
| --- | --- | --- |
| `--use_rabc` | 启用 RA-BC 样本加权 | `false` |
| `--rabc_progress_path` | 进度 parquet 文件的路径（从数据集自动检测） | 数据集中的 `sarm_progress.parquet` |
| `--rabc_head_mode` | 使用哪个 SARM 头的进度：`sparse` 或 `dense` | `sparse` |
| `--rabc_kappa` | 高质量样本的阈值 κ | `0.01` |

### 调整 RA-BC Kappa

`kappa` 参数是决定哪些样本获得完全权重（w=1）的阈值。理解如何调整它对于 RA-BC 有效工作至关重要。

**加权如何工作**

| 条件 | 重量 |
| --- | --- |
| `delta > kappa` | 1.0（硬阈值） |
| `0 ≤ delta ≤ kappa` | 等式 8 中的软权重 |
| `delta < 0` | 0.0（负进度） |

**诊断 kappa 问题**

在训练期间监控这些 WandB 指标

| 指标 | 健康范围 | 问题指示器 |
| --- | --- | --- |
| `rabc_mean_weight` | 0.3 - 0.8 | ≈ 1.0 意味着 kappa 太低 |
| `rabc_delta_mean` | > 0 | 应为正数 |
| `rabc_delta_std` | > 0 | 数据质量的方差 |

**如果 `rabc_mean_weight ≈ 1.0`：** 您的 kappa 太低了。大多数样本的 `delta > kappa` 并完全绕过了软加权。RA-BC 变得等同于普通的 BC。

**根据您的数据设置 kappa**

默认的 `kappa=0.01` 是为论文中的 T 恤折叠任务（30fps 下约 90 秒片段）调整的。对于您的数据集，请检查记录的 `rabc_delta_mean` 和 `rabc_delta_std`

```
# If delta_mean ≈ 0.03 and delta_std ≈ 0.02:
# Most deltas fall in range [0.01, 0.05]

# Option 1: Set kappa = delta_mean (medium selectivity)
--rabc_kappa=0.03

# Option 2: Set kappa = delta_mean + delta_std (high selectivity)
--rabc_kappa=0.05

# Option 3: Set kappa = delta_mean + 2*delta_std (very selective)
--rabc_kappa=0.07
```

**RA-BC 可能无效的情况**

如果您的数据集已经是高质量的（所有演示的进度一致），RA-BC 不会提供太多好处，因为没有东西需要过滤。

### 使用 RA-BC 进行多 GPU 训练

```
accelerate launch \
  --multi_gpu \
  --num_processes=4 \
  src/lerobot/scripts/lerobot_train.py \
  --dataset.repo_id=your-username/your-dataset \
  --policy.type=pi0 \
  --use_rabc=true \
  --rabc_kappa=0.01 \
  --output_dir=outputs/train/policy_rabc \
  --batch_size=32 \
  --steps=40000
```

---

## 提示与最佳实践

### 选择模式

* **从 `single_stage` 开始**进行快速实验 - 无标注开销
* 当您需要详细的进度跟踪，但任务没有明确的高级阶段时，请使用 **`dense_only`**
* 对于粗粒度和细粒度进度都有意义的复杂任务，请使用 **`dual`**

### 标注质量

1. **对子任务名称具体化**：不要只用“折叠”，请用“抓取近侧并向中心折叠”
2. **通过可视化进行验证**：在训练前务必检查几个片段
3. **一致的命名**：在所有片段中使用相同的子任务名称

### RA-BC

1. **先训练 SARM**：RA-BC 的质量完全取决于 SARM 的质量
2. **监控 `rabc_mean_weight`**：如果它 ≈ 1.0，增加 kappa（请参阅 [调整 RA-BC Kappa](sarm.md#tuning-ra-bc-kappa)）

---

## 引用

```
@article{chen2025sarm,
  title={SARM: Stage-Aware Reward Modeling for Long Horizon Robot Manipulation},
  author={Chen, Qianzhong and Yu, Justin and Schwager, Mac and Abbeel, Pieter and Shentu, Yide and Wu, Philipp},
  journal={arXiv preprint arXiv:2509.25358},
  year={2025}
}
```

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/sarm.mdx)
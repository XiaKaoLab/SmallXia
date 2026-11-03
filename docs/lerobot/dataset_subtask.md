# 来源

https://hugging-face.cn/docs/lerobot/dataset_subtask

# 在 LeRobot 数据集中使用子任务

机器人数据集中的子任务支持已被证明能有效提升机器人的推理和理解能力。子任务尤其适用于：

* **分层策略 (Hierarchical policies)**：构建包含子任务预测的策略，以实时可视化机器人的推理过程。
* **奖励建模 (Reward modeling)**：帮助奖励模型理解任务进展（例如：SARM 型阶段感知奖励模型）。
* **任务分解 (Task decomposition)**：将复杂的操纵任务拆解为原子化的、可解释的步骤。

LeRobotDataset 现已在数据集结构中支持子任务，与任务（tasks）并行存在。

## 什么是子任务？

如果说**任务**描述了整体目标（例如：“拿起苹果并放入篮子”），那么**子任务**则是将执行过程细化为更细粒度的步骤：

1. “靠近苹果”
2. “抓取苹果”
3. “提起苹果”
4. “移动到篮子”
5. “放下苹果”

数据集中的每一帧都可以标注相应的子任务，使模型能够学习并预测这些中间阶段。

![An overview of subtask annotation showing how frames are labeled with intermediate subtask stages](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/subtask-asset.png)

*图：子任务标注概览。*

**参考：** *Subtask-learning based for robot self-assembly in flexible collaborative assembly in manufacturing*, 原文，发布日期：2022年4月19日。

## 数据集结构

子任务信息存储在数据集元数据中。

```
my-dataset/
├── data/
│   └── ...
├── meta/
│   ├── info.json
│   ├── stats.json
│   ├── tasks.parquet
│   ├── subtasks.parquet      # Subtask index → subtask string mapping
│   └── episodes/
│       └── ...
└── videos/
    └── ...
```

### 子任务 Parquet 文件

`meta/subtasks.parquet` 文件将子任务索引映射到其自然语言描述。

| subtask\_index | subtask（索引列） |
| --- | --- |
| 0 | “靠近苹果” |
| 1 | “抓取苹果” |
| 2 | “提起苹果” |
| ... | ... |

### 帧级标注

数据集中的每一帧都可以包含一个引用子任务 Parquet 文件的 `subtask_index` 字段。

```
# Example frame data in the parquet file
{
    "index": 42,
    "timestamp": 1.4,
    "episode_index": 0,
    "task_index": 0,
    "subtask_index": 2,  # References "Lift the apple"
    "observation.state": [...],
    "action": [...],
}
```

## 为数据集标注子任务

我们提供了一个 HuggingFace Space，用于轻松地为任何 LeRobotDataset 标注子任务。

**<https://hugging-face.cn/spaces/lerobot/annotate>**

完成标注后：

1. 点击“Push to Hub”上传你标注好的数据集。
2. 你也可以按照 [github.com/huggingface/lerobot-annotate](https://github.com/huggingface/lerobot-annotate) 的说明在本地运行此标注工具。

## 加载带有子任务的数据集

当你加载带有子任务标注的数据集时，子任务信息会自动可用。

```
from lerobot.datasets.lerobot_dataset import LeRobotDataset

# Load a dataset with subtask annotations
dataset = LeRobotDataset("jadechoghari/collect-fruit-annotated")

# Access a sample
sample = dataset[100]

# The sample includes both task and subtask information
print(sample["task"])        # "Collect the fruit"
print(sample["subtask"])     # "Grasp the apple"
print(sample["task_index"])  # tensor(0)
print(sample["subtask_index"])  # tensor(2)
```

### 检查子任务支持

你可以检查数据集是否包含子任务标注。

```
# Check if subtasks are available
has_subtasks = (
    "subtask_index" in dataset.features
    and dataset.meta.subtasks is not None
)

if has_subtasks:
    print(f"Dataset has {len(dataset.meta.subtasks)} unique subtasks")
    print("Subtasks:", list(dataset.meta.subtasks.index))
```

## 使用子任务进行训练

### 使用 TokenizerProcessor

`TokenizerProcessor` 会自动处理视觉语言动作（VLA）模型的子任务分词。

```
from lerobot.processor.tokenizer_processor import TokenizerProcessor
from lerobot.processor.pipeline import ProcessorPipeline

# Create a tokenizer processor
tokenizer_processor = TokenizerProcessor(
    tokenizer_name_or_path="google/paligemma-3b-pt-224",
    padding="max_length",
    max_length=64,
)

# The processor will automatically tokenize subtasks if present in the batch
# and add them to the observation under:
# - "observation.subtask.tokens"
# - "observation.subtask.attention_mask"
```

当批次中存在子任务时，分词处理器会添加：

* `observation.subtask.tokens`：分词后的子任务文本。
* `observation.subtask.attention_mask`：子任务 token 的注意力掩码。

### 带有子任务的 DataLoader

```
import torch
from lerobot.datasets.lerobot_dataset import LeRobotDataset

dataset = LeRobotDataset("jadechoghari/collect-fruit-annotated")

dataloader = torch.utils.data.DataLoader(
    dataset,
    batch_size=16,
    shuffle=True,
)

for batch in dataloader:
    # Access subtask information in the batch
    subtasks = batch["subtask"]  # List of subtask strings
    subtask_indices = batch["subtask_index"]  # Tensor of subtask indices

    # Use for training hierarchical policies or reward models
    print(f"Batch subtasks: {set(subtasks)}")
```

## 带有子任务标注的示例数据集

尝试加载带有子任务标注的数据集。

```
from lerobot.datasets.lerobot_dataset import LeRobotDataset

# Example dataset with subtask annotations
dataset = LeRobotDataset("jadechoghari/collect-fruit-annotated")

# Explore the subtasks
print("Available subtasks:")
for subtask_name in dataset.meta.subtasks.index:
    print(f"  - {subtask_name}")

# Get subtask distribution
subtask_counts = {}
for i in range(len(dataset)):
    sample = dataset[i]
    subtask = sample["subtask"]
    subtask_counts[subtask] = subtask_counts.get(subtask, 0) + 1

print("\nSubtask distribution:")
for subtask, count in sorted(subtask_counts.items(), key=lambda x: -x[1]):
    print(f"  {subtask}: {count} frames")
```

## 用例

### 1. 分层策略训练

训练能够同时预测动作和当前子任务的策略。

```
class HierarchicalPolicy(nn.Module):
    def __init__(self, num_subtasks):
        super().__init__()
        self.action_head = nn.Linear(hidden_dim, action_dim)
        self.subtask_head = nn.Linear(hidden_dim, num_subtasks)

    def forward(self, observations):
        features = self.encoder(observations)
        actions = self.action_head(features)
        subtask_logits = self.subtask_head(features)
        return actions, subtask_logits
```

### 2. 阶段感知奖励建模 (SARM)

构建能够理解任务进展的奖励模型。

```
# SARM predicts:
# - Stage: Which subtask is being executed (discrete)
# - Progress: How far along the subtask (continuous 0-1)

class SARMRewardModel(nn.Module):
    def forward(self, observations):
        features = self.encoder(observations)
        stage_logits = self.stage_classifier(features)
        progress = self.progress_regressor(features)
        return stage_logits, progress
```

### 3. 进度可视化

通过追踪子任务进展来监控机器人执行过程。

```
def visualize_execution(model, observations):
    for t, obs in enumerate(observations):
        action, subtask_logits = model(obs)
        predicted_subtask = subtask_names[subtask_logits.argmax()]
        print(f"t={t}: Executing '{predicted_subtask}'")
```

## API 参考

### LeRobotDataset 属性

| 属性 | 类型 | 描述 |
| --- | --- | --- |
| `meta.subtasks` | `pd.DataFrame | None` | 将子任务名称映射到索引的 DataFrame |
| `features["subtask_index"]` | `字典` | 如果存在，则是 subtask\_index 的特征规范 |

### 样本键 (Sample Keys)

当有子任务时，每个样本包含：

| 键 | 类型 | 描述 |
| --- | --- | --- |
| `subtask_index` | `torch.Tensor` | 当前子任务的整数索引 |
| `subtask` | `字符串` | 自然语言子任务描述 |

## 相关资源

* [SARM 论文](https://arxiv.org/pdf/2509.25358) - 长程机器人操纵的阶段感知奖励建模
* [LeRobot 标注 Space](https://hugging-face.cn/spaces/lerobot/annotate) - 交互式标注工具
* [LeRobotDataset v3.0](lerobot-dataset-v3.md) - 数据集格式文档

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/dataset_subtask.mdx)
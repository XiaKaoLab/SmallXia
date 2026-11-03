# 来源

https://hugging-face.cn/docs/lerobot/lerobot-dataset-v3

# LeRobotDataset v3.0

`LeRobotDataset v3.0` 是机器人学习数据的标准格式。它提供了对多模态时间序列数据、传感器运动信号和多摄像头视频的统一访问，并在 Hugging Face Hub 上提供用于索引、搜索和可视化的丰富元数据。

本指南将引导您：

* 了解 v3.0 的设计和目录布局
* 录制数据集并将其推送到 Hub
* 使用 `LeRobotDataset` 加载训练数据集
* 使用 `StreamingLeRobotDataset` 在不下载的情况下流式传输数据集
* 在训练期间应用图像变换进行数据增强
* 将现有的 `v2.1` 数据集迁移到 `v3.0`

## v3 中的新特性

* **基于文件的存储**：每个 Parquet/MP4 文件包含多个回合（episode）（v2 为每个回合使用一个文件）。
* **关系元数据**：回合边界和查询通过元数据解析，而非文件名。
* **Hub 原生流式传输**：使用 `StreamingLeRobotDataset` 直接从 Hub 使用数据集。
* **更低的文件系统压力**：更少、更大的文件 ⇒ 更快的初始化和更少的规模化问题。
* **统一组织**：干净的目录布局，在数据和视频中具有一致的路径模板。

## 安装

`LeRobotDataset v3.0` 将包含在 `lerobot >= 0.4.0` 中。

在该稳定版发布之前，您可以按照 [源码构建指南](installation.md#from-source) 使用 main 分支。

## 录制数据集

运行以下命令使用 SO-101 录制数据集并推送到 Hub：

```
lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/tty.usbmodem585A0076841 \
  --robot.id=my_awesome_follower_arm \
  --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}}" \
  --teleop.type=so101_leader \
  --teleop.port=/dev/tty.usbmodem58760431551 \
  --teleop.id=my_awesome_leader_arm \
  --display_data=true \
  --dataset.repo_id=${HF_USER}/record-test \
  --dataset.num_episodes=5 \
  --dataset.single_task="Grab the black cube" \
  --dataset.streaming_encoding=true \
  # --dataset.vcodec=auto \
  --dataset.encoder_threads=2
```

有关更多详细信息，请参阅 [录制指南](il_robots.md#record-a-dataset)。

## 格式设计

v3 的核心原则是 **将存储与用户 API 解耦**：数据以高效方式存储（少量大文件），而公共 API 提供直观的回合级访问。

`v3` 有三大支柱：

1. **表格数据**：存储在 **Apache Parquet** 中的低维、高频信号（状态、动作、时间戳）。通过 `datasets` 栈进行内存映射或流式访问。
2. **视觉数据**：摄像头帧串联并编码为 **MP4**。同一回合的帧被分组；视频按摄像头分片以保持实用的大小。
3. **元数据**：JSON/Parquet 记录，描述模式（特征名称、数据类型、形状）、帧率、归一化统计数据以及 **回合细分**（共享 Parquet/MP4 文件中的起始/结束偏移量）。

> 为了扩展到数百万个回合，来自多个回合的表格行和视频帧被 **串联** 到更大的文件中。回合特定的视图通过 **元数据** 而非文件边界进行重建。

![LeRobotDataset v3 diagram](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobotdataset-v3/asset1datasetv3.png) 

从基于回合转变为基于文件的数据集

### 目录布局 (简化版)

* **`meta/info.json`**：规范模式（特征、形状/数据类型）、FPS、代码库版本以及定位数据/视频分片的 **路径模板**。
* **`meta/stats.json`**：用于归一化的全局特征统计数据（均值/标准差/最小值/最大值）；暴露为 `dataset.meta.stats`。
* **`meta/tasks.jsonl`**：自然语言任务描述，映射到任务条件策略的整数 ID。
* **`meta/episodes/`**：每回合记录（长度、任务、偏移量），以 **分块 Parquet** 形式存储以便扩展。
* **`data/`**：逐帧 **Parquet** 分片；每个文件通常包含 **许多个回合**。
* **`videos/`**：每个摄像头 **MP4** 分片；每个文件通常包含 **许多个回合**。

## 加载训练数据集

`LeRobotDataset` 返回 PyTorch 张量的 Python 字典，并与 `torch.utils.data.DataLoader` 集成。以下是展示其用法的代码示例：

```
import torch
from lerobot.datasets.lerobot_dataset import LeRobotDataset

repo_id = "yaak-ai/L2D-v3"

# 1) Load from the Hub (cached locally)
dataset = LeRobotDataset(repo_id)

# 2) Random access by index
sample = dataset[100]
print(sample)
# {
#   'observation.state': tensor([...]),
#   'action': tensor([...]),
#   'observation.images.front_left': tensor([C, H, W]),
#   'timestamp': tensor(1.234),
#   ...
# }

# 3) Temporal windows via delta_timestamps (seconds relative to t)
delta_timestamps = {
    "observation.images.front_left": [-0.2, -0.1, 0.0]  # 0.2s and 0.1s before current frame
}

dataset = LeRobotDataset(repo_id, delta_timestamps=delta_timestamps)

# Accessing an index now returns a stack for the specified key(s)
sample = dataset[100]
print(sample["observation.images.front_left"].shape)  # [T, C, H, W], where T=3

# 4) Wrap with a DataLoader for training
batch_size = 16
data_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size)

device = "cuda" if torch.cuda.is_available() else "cpu"
for batch in data_loader:
    observations = batch["observation.state"].to(device)
    actions = batch["action"].to(device)
    images = batch["observation.images.front_left"].to(device)
    # model.forward(batch)
```

## 流式传输数据集 (无需下载)

使用 `StreamingLeRobotDataset` 直接从 Hub 进行迭代，无需本地副本。这允许流式传输大型数据集，而无需将其下载到磁盘或加载到内存中，这是新数据集格式的一项关键特性。

```
from lerobot.datasets.streaming_dataset import StreamingLeRobotDataset

repo_id = "yaak-ai/L2D-v3"
dataset = StreamingLeRobotDataset(repo_id)  # streams directly from the Hub
```

![StreamingLeRobotDataset](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobotdataset-v3/streaming-lerobot.png) 

直接从 Hub 流式传输以进行实时训练。

## 图像变换

图像变换是训练期间应用于摄像头帧的数据增强，以提高模型的鲁棒性和泛化能力。LeRobot 支持各种变换，包括亮度、对比度、饱和度、色调和锐度调整。

### 在数据集创建/录制期间使用变换

目前，变换 **仅在训练时** 应用，而不在录制期间应用。当您创建或录制数据集时，存储的是原始图像，不含变换。这允许您以后试验不同的增强方案，而无需重新录制数据。

### 向现有数据集添加变换 (API)

加载训练数据集时使用 `image_transforms` 参数：

```
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.transforms import ImageTransforms, ImageTransformsConfig, ImageTransformConfig

# Option 1: Use default transform configuration (disabled by default)
transforms_config = ImageTransformsConfig(
    enable=True,  # Enable transforms
    max_num_transforms=3,  # Apply up to 3 transforms per frame
    random_order=False,  # Apply in standard order
)
transforms = ImageTransforms(transforms_config)

dataset = LeRobotDataset(
    repo_id="your-username/your-dataset",
    image_transforms=transforms
)

# Option 2: Create custom transform configuration
custom_transforms_config = ImageTransformsConfig(
    enable=True,
    max_num_transforms=2,
    random_order=True,
    tfs={
        "brightness": ImageTransformConfig(
            weight=1.0,
            type="ColorJitter",
            kwargs={"brightness": (0.7, 1.3)}  # Adjust brightness range
        ),
        "contrast": ImageTransformConfig(
            weight=2.0,  # Higher weight = more likely to be selected
            type="ColorJitter",
            kwargs={"contrast": (0.8, 1.2)}
        ),
        "sharpness": ImageTransformConfig(
            weight=0.5,  # Lower weight = less likely to be selected
            type="SharpnessJitter",
            kwargs={"sharpness": (0.3, 2.0)}
        ),
    }
)

dataset = LeRobotDataset(
    repo_id="your-username/your-dataset",
    image_transforms=ImageTransforms(custom_transforms_config)
)

# Option 3: Use pure torchvision transforms
from torchvision.transforms import v2

torchvision_transforms = v2.Compose([
    v2.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
    v2.GaussianBlur(kernel_size=3, sigma=(0.1, 2.0)),
])

dataset = LeRobotDataset(
    repo_id="your-username/your-dataset",
    image_transforms=torchvision_transforms
)
```

### 可用变换类型

LeRobot 提供几种变换类型：

* **`ColorJitter`**：调整亮度、对比度、饱和度和色调
* **`SharpnessJitter`**：随机调整图像锐度
* **`Identity`**：不进行变换 (用于测试)

您也可以通过将任何 `torchvision.transforms.v2` 变换直接传递给 `image_transforms` 参数来使用它。

### 配置选项

* **`enable`**：启用/禁用变换 (默认值：`False`)
* **`max_num_transforms`**：每帧应用的最大变换数 (默认值：`3`)
* **`random_order`**：以随机顺序应用变换 vs 标准顺序 (默认值：`False`)
* **`weight`**：每个变换的采样概率 (越高 = 越可能，如果权重之和不为 1，它们将被归一化)
* **`kwargs`**：变换特定参数 (例如亮度范围)

### 可视化变换

使用可视化脚本预览变换如何影响您的数据：

```
lerobot-imgtransform-viz \
  --repo-id=your-username/your-dataset \
  --output-dir=./transform_examples \
  --n-examples=5
```

这将保存显示每种变换效果的示例图像，帮助您调整参数。

### 最佳实践

* **开始时保持保守**：从较小范围开始（例如亮度 0.9-1.1），然后逐渐增加
* **先测试**：使用可视化脚本确保变换看起来合理
* **监控训练**：如果过于激进，强增强可能会损害性能
* **匹配您的领域**：如果您的机器人运行在变化的光照下，使用亮度/对比度变换
* **明智组合**：同时使用过多变换可能会使训练不稳定

## 迁移 v2.1 → v3.0

转换器将每回合文件聚合为更大的分片，并写入回合偏移量/元数据。按照以下说明转换您的数据集：

```
# Pre-release build with v3 support:
pip install "https://github.com/huggingface/lerobot/archive/33cad37054c2b594ceba57463e8f11ee374fa93c.zip"

# Convert an existing v2.1 dataset hosted on the Hub:
python -m lerobot.datasets.v30.convert_dataset_v21_to_v30 --repo-id=<HF_USER/DATASET_ID>
```

**它的作用**

* 聚合 parquet 文件：`episode-0000.parquet`, `episode-0001.parquet`, … → **`file-0000.parquet`**, …
* 聚合 mp4 文件：`episode-0000.mp4`, `episode-0001.mp4`, … → **`file-0000.mp4`**, …
* 使用每回合长度、任务、字节/帧偏移量更新 `meta/episodes/*` (分块 Parquet)。

## 常见问题

### 推送前务必调用 finalize()

在创建或录制数据集时，您 **必须** 调用 `dataset.finalize()` 以正确关闭 parquet 写入器。有关更多详细信息，请参阅 [PR #1903](https://github.com/huggingface/lerobot/pull/1903)。

```
from lerobot.datasets.lerobot_dataset import LeRobotDataset

# Create dataset and record episodes
dataset = LeRobotDataset.create(...)

for episode in range(num_episodes):
    # Record frames
    for frame in episode_data:
        dataset.add_frame(frame)
    dataset.save_episode()

# Call finalize() when done recording and before push_to_hub()
dataset.finalize()  # Closes parquet writers, writes metadata footers
dataset.push_to_hub()
```

**为什么这是必要的？**

数据集 v3.0 为提高效率，使用带有缓冲元数据的增量 parquet 写入。`finalize()` 方法的作用：

* 将所有缓冲的回合元数据刷新到磁盘
* 关闭 parquet 写入器以写入页脚元数据，否则 parquet 文件将损坏
* 确保数据集可加载有效

如果不调用 `finalize()`，您的 parquet 文件将不完整，数据集将无法正常加载。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/lerobot-dataset-v3.mdx)
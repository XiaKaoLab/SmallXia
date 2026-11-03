# 来源

https://hugging-face.cn/docs/lerobot/porting_datasets_v3

# 将大型数据集迁移到 LeRobot Dataset v3.0

本教程解释了如何将大规模机器人数据集迁移到 LeRobot Dataset v3.0 格式。我们将使用 **DROID 1.0.1** 数据集作为主要示例，演示如何处理跨 SLURM 集群的数千个分片、TB 级大小的数据集。

## 文件组织：v2.1 与 v3.0

数据集 v3.0 从根本上改变了数据的组织和存储方式

**v2.1 结构（基于回合）**:

```
dataset/
├── data/chunk-000/episode_000000.parquet
├── data/chunk-000/episode_000001.parquet
├── videos/chunk-000/camera/episode_000000.mp4
└── meta/episodes.jsonl
```

**v3.0 结构（基于文件）**:

```
dataset/
├── data/chunk-000/file-000.parquet        # Multiple episodes per file
├── videos/camera/chunk-000/file-000.mp4   # Consolidated video chunks
└── meta/episodes/chunk-000/file-000.parquet  # Structured metadata
```

从单个回合文件到基于文件的块的这一转变，极大地提高了性能并减少了存储开销。

## 数据集 v3.0 的新特性

数据集 v3.0 为处理大型数据集引入了重大改进

### 🏗️ 增强的文件组织

* **基于文件的结构**：回合现在被分组成块文件，而不是单个回合文件
* **可配置的文件大小**：适用于数据文件和视频文件
* **提高存储效率**：更好的压缩效果并减少了开销

### 📊 现代元数据管理

* **基于 Parquet 的元数据**：用高效的 Parquet 格式取代了 JSON Lines
* **结构化的回合访问**：通过 `dataset.meta.episodes` 直接访问 pandas DataFrame
* **单回合统计**：在回合级别增强了统计跟踪

### 🚀 性能提升

* **内存映射访问**：通过 PyArrow 内存映射改进了 RAM 使用率
* **更快的加载速度**：显著缩短了数据集初始化时间
* **更好的可扩展性**：专为包含数百万个回合的数据集设计

## 先决条件

在迁移大型数据集之前，请确保您具备以下条件

* **安装了支持 v3.0 的 LeRobot**。请参考我们的[安装指南](installation.md)。
* **充足的存储空间**：原始数据集可能非常大（例如 DROID 需要 2TB）
* **集群访问权限**（建议用于大型数据集）：SLURM 或类似的作业调度器
* **数据集特定依赖项**：对于 DROID，您需要 TensorFlow Dataset 实用程序

## 了解 DROID 数据集

[DROID 1.0.1](https://droid-dataset.github.io/droid/the-droid-dataset) 是大规模机器人数据集的一个极佳示例

* **大小**：1.7TB (RLDS 格式)，8.7TB (原始数据)
* **结构**：2048 个预定义的 TensorFlow 数据集分片
* **内容**：来自 Franka Emika Panda 机器人的 76,000+ 条机器人操作轨迹
* **范围**：跨越多个环境和物体的真实世界操作任务
* **格式**：最初为 TensorFlow Records/RLDS 格式，需要转换为 LeRobot 格式
* **托管**：可通过 `gsutil` 进行公开访问的 Google Cloud Storage

该数据集包含多样化的操作演示，包括：

* 多个摄像头视角（手腕摄像头、外部摄像头）
* 自然语言任务描述
* 机器人的本体感受状态和动作
* 成功/失败的标注

### DROID 特性模式

```
DROID_FEATURES = {
    # Episode markers
    "is_first": {"dtype": "bool", "shape": (1,)},
    "is_last": {"dtype": "bool", "shape": (1,)},
    "is_terminal": {"dtype": "bool", "shape": (1,)},

    # Language instructions
    "language_instruction": {"dtype": "string", "shape": (1,)},
    "language_instruction_2": {"dtype": "string", "shape": (1,)},
    "language_instruction_3": {"dtype": "string", "shape": (1,)},

    # Robot state
    "observation.state.gripper_position": {"dtype": "float32", "shape": (1,)},
    "observation.state.cartesian_position": {"dtype": "float32", "shape": (6,)},
    "observation.state.joint_position": {"dtype": "float32", "shape": (7,)},

    # Camera observations
    "observation.images.wrist_left": {"dtype": "image"},
    "observation.images.exterior_1_left": {"dtype": "image"},
    "observation.images.exterior_2_left": {"dtype": "image"},

    # Actions
    "action.gripper_position": {"dtype": "float32", "shape": (1,)},
    "action.cartesian_position": {"dtype": "float32", "shape": (6,)},
    "action.joint_position": {"dtype": "float32", "shape": (7,)},

    # Standard LeRobot format
    "observation.state": {"dtype": "float32", "shape": (8,)},  # joints + gripper
    "action": {"dtype": "float32", "shape": (8,)},  # joints + gripper
}
```

## 方法 1：单机迁移

### 第 1 步：安装依赖项

专门针对 DROID

```
pip install tensorflow
pip install tensorflow_datasets
```

对于其他数据集，请安装适合您源格式的读取器。

### 第 2 步：下载原始数据

使用 `gsutil` 从 Google Cloud Storage 下载 DROID

```
# Install Google Cloud SDK if not already installed
# https://cloud.google.com/sdk/docs/install

# Download the full RLDS dataset (1.7TB)
gsutil -m cp -r gs://gresearch/robotics/droid/1.0.1 /your/data/

# Or download just the 100-episode sample (2GB) for testing
gsutil -m cp -r gs://gresearch/robotics/droid_100 /your/data/
```

> 大型数据集需要大量的时间和存储空间
>
> * **完整的 DROID (1.7TB)**：下载可能需要几天，具体取决于带宽
> * **处理时间**：在本地迁移完整数据集需要 7 天以上
> * **上传时间**：推送到 Hugging Face Hub 需要 3 天以上
> * **本地存储**：处理后的 LeRobot 格式约占 400GB

### 第 3 步：迁移数据集

```
python examples/port_datasets/port_droid.py \
    --raw-dir /your/data/droid/1.0.1 \
    --repo-id your_id/droid_1.0.1 \
    --push-to-hub
```

### 开发与测试

为了进行开发，您可以迁移单个分片

```
python examples/port_datasets/port_droid.py \
    --raw-dir /your/data/droid/1.0.1 \
    --repo-id your_id/droid_1.0.1_test \
    --num-shards 2048 \
    --shard-index 0
```

这种方法适用于较小的数据集或测试，但大型数据集需要集群计算。

## 方法 2：SLURM 集群迁移（推荐）

对于像 DROID 这样的大型数据集，跨多个节点的并行处理可以极大地缩短处理时间。

### 第 1 步：安装集群依赖项

```
pip install datatrove  # Hugging Face's distributed processing library
```

### 第 2 步：配置您的 SLURM 环境

查询您的分区信息

```
sinfo --format="%R"  # List available partitions
sinfo -N -p your_partition -h -o "%N cpus=%c mem=%m"  # Check resources
```

选择一个 **CPU 分区** —— 数据集迁移不需要 GPU。

### 第 3 步：启动并行迁移作业

```
python examples/port_datasets/slurm_port_shards.py \
    --raw-dir /your/data/droid/1.0.1 \
    --repo-id your_id/droid_1.0.1 \
    --logs-dir /your/logs \
    --job-name port_droid \
    --partition your_partition \
    --workers 2048 \
    --cpus-per-task 8 \
    --mem-per-cpu 1950M
```

#### 参数指南

* **`--workers`**：并行作业的数量（对于 DROID 的分片数，最大为 2048）
* **`--cpus-per-task`**：建议使用 8 个 CPU 以实现帧编码并行化
* **`--mem-per-cpu`**：加载原始帧需要约 16GB 总内存 (8×1950M)

> 在启动数千个作业之前，先尝试少量 worker（例如 100 个）来测试您的集群配置。

### 第 4 步：监控进度

检查正在运行的作业

```
squeue -u $USER
```

监控总体进度

```
jobs_status /your/logs
```

查看单个作业日志

```
less /your/logs/port_droid/slurm_jobs/JOB_ID_WORKER_ID.out
```

调试失败的作业

```
failed_logs /your/logs/port_droid
```

### 第 5 步：聚合分片

待所有迁移作业完成后

```
python examples/port_datasets/slurm_aggregate_shards.py \
    --repo-id your_id/droid_1.0.1 \
    --logs-dir /your/logs \
    --job-name aggr_droid \
    --partition your_partition \
    --workers 2048 \
    --cpus-per-task 8 \
    --mem-per-cpu 1950M
```

### 第 6 步：上传至 Hub

```
python examples/port_datasets/slurm_upload.py \
    --repo-id your_id/droid_1.0.1 \
    --logs-dir /your/logs \
    --job-name upload_droid \
    --partition your_partition \
    --workers 50 \
    --cpus-per-task 4 \
    --mem-per-cpu 1950M
```

> 上传使用的 worker 较少 (50)，因为它是受网络带宽限制而非计算资源限制。

## 数据集 v3.0 文件结构

完成后的数据集将具有这种现代化的结构

```
dataset/
├── meta/
│   ├── episodes/
│   │   └── chunk-000/
│   │       └── file-000.parquet    # Episode metadata
│   ├── tasks.parquet               # Task definitions
│   ├── stats.json                  # Aggregated statistics
│   └── info.json                   # Dataset information
├── data/
│   └── chunk-000/
│       └── file-000.parquet        # Consolidated episode data
└── videos/
    └── camera_key/
        └── chunk-000/
            └── file-000.mp4        # Consolidated video files
```

这种结构取代了旧有的“每个文件一个回合”的形式，取而代之的是高效且大小适中的块文件。

## 从数据集 v2.1 迁移

如果您已有 v2.1 格式的数据集，请使用迁移工具

```
python src/lerobot/datasets/v30/convert_dataset_v21_to_v30.py \
    --repo-id your_id/existing_dataset
```

该工具将自动：

* 将文件结构转换为 v3.0 格式
* 将元数据从 JSON Lines 迁移到 Parquet
* 聚合统计数据并创建单回合统计
* 更新版本信息

## 性能优势

数据集 v3.0 为大型数据集提供了显著的改进

* **更快的加载速度**：初始化时间缩短了 3-5 倍
* **内存效率**：通过内存映射实现了更好的 RAM 使用率
* **可扩展的处理**：能够高效处理数百万个回合
* **存储优化**：减少了文件数量并改进了压缩效果

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/porting_datasets_v3.mdx)
# 来源

https://hugging-face.cn/docs/lerobot/using_dataset_tools

# 使用数据集工具

本指南涵盖了 LeRobot 中用于修改和编辑现有数据集的工具实用程序。

## 概述

LeRobot 提供了多种用于操作数据集的实用程序：

1. **删除片段 (Delete Episodes)** - 从数据集中移除特定的片段
2. **分割数据集 (Split Dataset)** - 将一个数据集拆分为多个较小的数据集
3. **合并数据集 (Merge Datasets)** - 将多个数据集组合成一个。数据集必须具有相同的特征，片段将按照 `repo_ids` 中指定的顺序进行连接
4. **添加特征 (Add Features)** - 向数据集添加新特征
5. **移除特征 (Remove Features)** - 从数据集中移除特征
6. **转换为视频 (Convert to Video)** - 将基于图像的数据集转换为视频格式以实现高效存储
7. **查看数据集信息 (Show the Info of Datasets)** - 查看数据集摘要信息，例如片段数量等。

核心实现位于 `lerobot.datasets.dataset_tools` 中。有关如何使用工具 API 的详细示例脚本，请参阅 `examples/dataset/use_dataset_tools.py`。

## 命令行工具：lerobot-edit-dataset

`lerobot-edit-dataset` 是一个用于编辑数据集的命令行脚本。它可用于删除片段、分割数据集、合并数据集、添加特征、移除特征以及将图像数据集转换为视频格式。

运行 `lerobot-edit-dataset --help` 以获取有关各项操作配置的更多信息。

### 用法示例

#### 删除片段

从数据集中移除特定片段。这对于过滤掉不需要的数据非常有用。

```
# Delete episodes 0, 2, and 5 (modifies original dataset)
lerobot-edit-dataset \
    --repo_id lerobot/pusht \
    --operation.type delete_episodes \
    --operation.episode_indices "[0, 2, 5]"

# Delete episodes and save to a new dataset (preserves original dataset)
lerobot-edit-dataset \
    --repo_id lerobot/pusht \
    --new_repo_id lerobot/pusht_after_deletion \
    --operation.type delete_episodes \
    --operation.episode_indices "[0, 2, 5]"
```

#### 分割数据集

将数据集划分为多个子集。

```
# Split by fractions (e.g. 80% train, 20% test, 20% val)
lerobot-edit-dataset \
    --repo_id lerobot/pusht \
    --operation.type split \
    --operation.splits '{"train": 0.8, "test": 0.2, "val": 0.2}'

# Split by specific episode indices
lerobot-edit-dataset \
    --repo_id lerobot/pusht \
    --operation.type split \
    --operation.splits '{"task1": [0, 1, 2, 3], "task2": [4, 5]}'
```

对分割名称没有限制，由用户决定。生成的数据集将保存为在原仓库 ID 后附加分割名称的形式，例如 `lerobot/pusht_train`, `lerobot/pusht_task1`, `lerobot/pusht_task2`。

#### 合并数据集

将多个数据集组合成一个数据集。

```
# Merge train and validation splits back into one dataset
lerobot-edit-dataset \
    --repo_id lerobot/pusht_merged \
    --operation.type merge \
    --operation.repo_ids "['lerobot/pusht_train', 'lerobot/pusht_val']"
```

#### 移除特征

从数据集中移除特征。

```
# Remove a camera feature
lerobot-edit-dataset \
    --repo_id lerobot/pusht \
    --operation.type remove_feature \
    --operation.feature_names "['observation.images.top']"
```

#### 转换为视频

将基于图像的数据集转换为视频格式，创建一个新的 LeRobotDataset，其中图像存储为视频。这对于减少存储需求和提高数据加载性能非常有用。新数据集将具有与原始数据集完全相同的结构，但图像将编码为符合 LeRobot 格式要求的 MP4 视频。

```
# Local-only: Save to a custom output directory (no hub push)
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --operation.type convert_image_to_video \
    --operation.output_dir /path/to/output/pusht_video

# Save with new repo_id (local storage)
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --new_repo_id lerobot/pusht_video \
    --operation.type convert_image_to_video

# Convert and push to Hugging Face Hub
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --new_repo_id lerobot/pusht_video \
    --operation.type convert_image_to_video \
    --push_to_hub true

# Convert with custom video codec and quality settings
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --operation.type convert_image_to_video \
    --operation.output_dir outputs/pusht_video \
    --operation.vcodec libsvtav1 \
    --operation.pix_fmt yuv420p \
    --operation.g 2 \
    --operation.crf 30

# Convert only specific episodes
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --operation.type convert_image_to_video \
    --operation.output_dir outputs/pusht_video \
    --operation.episode_indices "[0, 1, 2, 5, 10]"

# Convert with multiple workers for parallel processing
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --operation.type convert_image_to_video \
    --operation.output_dir outputs/pusht_video \
    --operation.num_workers 8

# For memory-constrained systems, users can now specify limits:
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --operation.type convert_to_video \
    --operation.max_episodes_per_batch 50 \
    --operation.max_frames_per_batch 10000
```

**参数量**

* `output_dir`: 自定义输出目录（可选 - 默认使用 `new_repo_id` 或 `{repo_id}_video`）
* `vcodec`: 使用的视频编码器 - 选项：`h264`, `hevc`, `libsvtav1` (默认: `libsvtav1`)
* `pix_fmt`: 像素格式 - 选项：`yuv420p`, `yuv444p` (默认: `yuv420p`)
* `g`: 图片组 (GOP) 大小 - 数值越小，质量越好但文件越大 (默认: 2)
* `crf`: 恒定码率因子 - 数值越小，质量越好但文件越大，0 为无损 (默认: 30)
* `fast_decode`: 快速解码调优选项 (默认: 0)
* `episode_indices`: 要转换的特定片段列表 (默认: 所有片段)
* `num_workers`: 处理的并行工作线程数 (默认: 4)

**注意：**生成的数据集将是一个标准的 LeRobotDataset，所有摄像机数据都编码为位于 `videos/` 目录下的视频，而 parquet 文件仅包含元数据（不含原始图像数据）。所有片段、统计信息和任务都将被保留。

### 查看数据集信息

显示数据集信息，例如片段数量、帧数、文件大小等。不会对数据集进行任何更改。

```
# Show dataset information without feature details
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --operation.type info \

# Show dataset information with feature details
lerobot-edit-dataset \
    --repo_id lerobot/pusht_image \
    --operation.type info \
    --operation.show_features true
```

**参数量**

* `parameters`: 控制是否显示包含详细特征信息的数据集信息的标志。(默认=false)

### 推送到 Hub

在任何命令中添加 `--push_to_hub true` 标志，即可自动将生成的数据集上传到 Hugging Face Hub。

```
lerobot-edit-dataset \
    --repo_id lerobot/pusht \
    --new_repo_id lerobot/pusht_after_deletion \
    --operation.type delete_episodes \
    --operation.episode_indices "[0, 2, 5]" \
    --push_to_hub true
```

还有一个用于向数据集添加特征的工具，该功能尚未包含在 `lerobot-edit-dataset` 中。

# 数据集可视化

## 在线可视化

当您使用 `lerobot` 记录数据集时，除非另有说明，它会自动上传到 Hugging Face Hub。要在线查看数据集，请使用我们的 **LeRobot 数据集可视化工具**，地址：<https://hugging-face.cn/spaces/lerobot/visualize_dataset>

## 本地可视化

您还可以使用我们的命令行工具在本地可视化数据集中的片段。

**来自 Hugging Face Hub**

```
lerobot-dataset-viz \
    --repo-id lerobot/pusht \
    --episode-index 0
```

**从本地文件夹：** 添加 `--root` 选项并设置 `--mode local`。例如，要搜索 `./my_local_data_dir/lerobot/pusht`

```
lerobot-dataset-viz \
    --repo-id lerobot/pusht \
    --root ./my_local_data_dir \
    --mode local \
    --episode-index 0
```

执行后，该工具将打开 `rerun.io` 并显示所选片段的摄像机流、机器人状态和动作。

对于高级用法（包括可视化存储在远程服务器上的数据集），请运行

```
lerobot-dataset-viz --help
```

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/using_dataset_tools.mdx)
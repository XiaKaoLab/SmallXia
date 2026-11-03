# 来源

https://hugging-face.cn/docs/lerobot/streaming_video_encoding

# 流式视频编码指南

## 1. 概述

流式视频编码消除了视频数据集记录过程中传统的 PNG 往返。无需进行以下步骤：

1. 捕获帧 -> 写入 PNG 到磁盘 -> (在回合结束时) 读取 PNG -> 编码为 MP4 -> 删除 PNG

帧可以在捕获过程中进行实时编码：

1. 捕获帧 -> 排队到编码器线程 -> 直接编码为 MP4

这使得 `save_episode()` 几乎瞬时完成（在回合结束时，视频已经编码完成），并消除了以前在回合之间发生的阻塞等待，特别是在长回合中使用多个相机时。

## 2. 调整参数

| 参数 | CLI 标志 | 类型 | 默认 | 描述 |
| --- | --- | --- | --- | --- |
| `streaming_encoding` | `--dataset.streaming_encoding` | `布尔值` | `True` | 在捕获期间启用实时编码 |
| `vcodec` | `--dataset.vcodec` | `字符串` | `"libsvtav1"` | 视频编解码器。`"auto"` 会检测最佳硬件编码器 |
| `encoder_threads` | `--dataset.encoder_threads` | `int \| None` | `None` (自动) | 每个编码器实例的线程数。`None` 将由编解码器决定 |
| `encoder_queue_maxsize` | `--dataset.encoder_queue_maxsize` | `int` | `60` | 每个相机的最大缓冲帧数（在 30fps 下约为 2 秒）。消耗内存 |

## 3. 性能考量

流式编码意味着 CPU 是在捕获循环**期间**对视频进行编码，而不是在此之后。这产生了一个必须在以下各项之间共享的 CPU 预算：

* **控制循环**（读取相机、控制机器人、写入非视频数据）
* **编码器线程**（每个相机一个线程池）
* **Rerun 可视化**（如果启用）
* **操作系统和其他进程**

### 分辨率与相机数量的影响

| 设置 | 吞吐量 (像素/秒) | CPU 编码负载 | 备注 |
| --- | --- | --- | --- |
| 2 个相机 x 640x480x3 @30fps | 55M | 低 | 适用于大多数系统 |
| 2 个相机 x 1280x720x3 @30fps | 165M | 中等 | 在现代系统上运行轻松 |
| 2 个相机 x 1920x1080x3 @30fps | 373M | 高 | 需要强大的高端 CPU |

### encoder\_threads 调整

此参数控制每个编码器实例在内部使用多少个线程

* **较高值**（例如 4-5）：编码速度更快，但每个相机消耗更多 CPU 核心。适用于拥有多核心的高端系统。
* **较低值**（例如 1-2）：每个相机占用更少 CPU，从而为捕获和可视化释放核心。适用于低分辨率图像和性能尚可的 CPU。
* **`None` (默认)**：让编解码器决定。信息可在编解码器日志中找到。

### 背压与丢帧

每个相机都有一个有界队列（`encoder_queue_maxsize`，默认 60 帧）。当编码器无法跟上时：

1. 队列会被填满（消耗内存）
2. 新帧将被**丢弃**（不会阻塞）——捕获循环会不间断地继续运行
3. 会记录一条警告：`"Encoder queue full for {camera}, dropped N frame(s)"`
4. 在回合结束时，会报告每个相机丢弃的总帧数

### 编码器滞后的症状

* **系统感觉卡顿和冻结**：所有 CPU 占用率达到 100%
* 日志中出现**丢帧警告**，或者记录的数据集中的帧数/FPS 低于预期
* **机器人动作断断续续**：如果 CPU 严重超载，甚至捕获循环也可能会受到影响
* **累积的 Rerun 延迟**：可视化滞后于实时画面

## 4. 硬件加速编码

### 何时使用

在以下情况下使用硬件编码：

* CPU 是瓶颈（丢帧、机器人动作不连贯、可视化延迟）
* 您拥有兼容的硬件（GPU 或专用编码器）
* 您正在以高吞吐量进行记录（高分辨率或配备多台相机）

### 选择编解码器

| 编解码器 | CPU 使用率 | 文件大小 | 质量 | 备注 |
| --- | --- | --- | --- | --- |
| `libsvtav1` (默认) | 高 | 最小 | 最佳 | 默认。压缩率最好，但最耗 CPU |
| `h264` | 中型 | 大约大 30-50% | 很好 | 软件 H.264。较低的 CPU 占用 |
| 硬件编码器 | 极低 | 最大 | 很好 | 分流到专用硬件。最适合 CPU 受限的系统 |

### 可用的硬件编码器

| 编码器 | 平台 | 硬件 | CLI 值 |
| --- | --- | --- | --- |
| `h264_videotoolbox` | macOS | Apple Silicon / Intel | `--dataset.vcodec=h264_videotoolbox` |
| `hevc_videotoolbox` | macOS | Apple Silicon / Intel | `--dataset.vcodec=hevc_videotoolbox` |
| `h264_nvenc` | Linux/Windows | NVIDIA GPU | `--dataset.vcodec=h264_nvenc` |
| `hevc_nvenc` | Linux/Windows | NVIDIA GPU | `--dataset.vcodec=hevc_nvenc` |
| `h264_vaapi` | Linux | Intel/AMD GPU | `--dataset.vcodec=h264_vaapi` |
| `h264_qsv` | Linux/Windows | Intel Quick Sync | `--dataset.vcodec=h264_qsv` |
| `auto` | Any | 探测系统以查找可用的硬件编码器。如果未找到硬件编码器，则回退到 `libsvtav1` | `--dataset.vcodec=auto` |

> 为了使用硬件加速编码器，您可能需要升级 GPU 驱动程序。

> 默认使用 `libsvtav1`，因为它能提供最佳的训练性能；其他编解码器（vcodec）可以降低 CPU 使用率并加快速度，但它们通常会产生更大的文件，并且可能会影响训练时间。

## 5. 故障排除

| 症状 | 可能原因 | 解决方法 |
| --- | --- | --- |
| 系统冻结、机器人动作断断续续或 Rerun 可视化延迟 | CPU 耗尽（100% 负载使用率） | 关闭其他应用，减少编码吞吐量，降低 `encoder_threads`，使用 `h264`，使用 `display_data=False`。如果 CPU 仍然保持在 100%，则可能说明它无法满足您的配置需求，请考虑使用 `--dataset.streaming_encoding=false` 或硬件编码 (`--dataset.vcodec=auto`) |
| “Encoder queue full” 警告或数据集丢帧 | 编码器无法跟上（队列溢出） | 如果 CPU 未达到 100%：增加 `encoder_threads`、增加 `encoder_queue_maxsize` 或使用硬件编码 (`--dataset.vcodec=auto`)。 |
| 高内存占用 | 队列填充速度快于编码速度 | `encoder_threads` 过低或 CPU 性能不足。减少 `encoder_queue_maxsize` 或使用硬件编码 |
| 视频文件过大 | 使用了硬件编码器或 H.264 | 预期的权衡。如果 CPU 允许，请切换到 `libsvtav1` |
| `save_episode()` 仍然很慢 | `streaming_encoding` 为 `False` | 设置 `--dataset.streaming_encoding=true` |
| 编码器线程崩溃 | 编解码器不可用或设置无效 | 检查 `vcodec` 是否已安装，尝试 `--dataset.vcodec=auto` |
| 录制的数据集丢失帧 | CPU/GPU 资源耗尽或偶尔的负载峰值 | 如果丢失了大约 5% 的帧，说明您的系统可能已经超载 — 请遵循上述建议。如果丢失的帧较少（约 2%），可能是由于偶尔的瞬时负载峰值（通常在启动时）引起的，可以认为是符合预期的。 |

## 6. 推荐配置

这些估算是保守的；我们建议在您的设备上进行测试——从低负载开始，然后逐渐增加。

### 高端系统：现代 12+ 核心 (24+ 线程)

约 250-500M 像素/秒的吞吐量对于 CPU 来说应该比较轻松。为了获得更好的效果，如果可用，请尝试硬件编码。

```
# 3camsx 1280x720x3 @30fps: Defaults work well. Optionally increase encoder parallelism.
# 2camsx 1920x1080x3 @30fps: Defaults work well. Optionally increase encoder parallelism.
lerobot-record --dataset.encoder_threads=5 ...

# 3camsx 1920x1080x3 @30fps: Might require some tuning.
```

### 中端系统：现代 8+ 核心 (16+ 线程) 或 Apple Silicon

在 CPU 中应该可以实现约 80-300M 像素/秒的吞吐量。

```
# 3camsx 640x480x3 @30fps: Defaults work well. Optionally decrease encoder parallelism.
# 2camsx 1280x720x3 @30fps: Defaults work well. Optionally decrease encoder parallelism.
lerobot-record --dataset.encoder_threads=2 ...

# 2camsx 1920x1080x3 @30fps: Might require some tuning.
```

### 低资源系统：现代 4+ 核心 (8+ 线程) 或 树莓派 5

在资源非常受限的系统上，流式编码可能会与捕获循环产生过大的竞争。禁用它将回退到基于 PNG 的方法，其中编码发生在回合之间（这会造成阻塞，但不会干扰捕获）。或者，以较低的吞吐量进行记录，以同时减少捕获和编码负载。也可以考虑将编解码器更改为 `h264` 并使用批量编码。

```
# 2camsx 640x480x3 @30fps: Requires some tuning.

# Use H.264, disable streaming, consider batching encoding
lerobot-record --dataset.vcodec=h264 --dataset.streaming_encoding=false ...
```

## 7. 结语

性能最终取决于您的具体配置——每秒帧数、分辨率、CPU 核心数和负载、可用内存、回合长度以及您选择的编码器。请务必使用目标工作负载进行测试，留意您的 CPU 和系统能力，并合理调整 `encoder_threads`、`encoder_queue_maxsize` 和 `vcodec`。话虽如此，一种常见的实用配置（适用于许多应用）是三个 640×480x3 @30fps 的相机；这在现代系统中配合默认的流式视频编码设置通常运行良好。请务必通过将视频时长与 CLI 命令行显示的回合时长进行对比，并确认行数等于 FPS × CLI 时长，来验证记录的数据集是否健康。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/streaming_video_encoding.mdx)
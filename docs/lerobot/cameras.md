# 来源

https://hugging-face.cn/docs/lerobot/cameras

# 摄像头

LeRobot 提供了多种视频采集选项

| 分类 | 支持的摄像头 |
| --- | --- |
| `OpenCVCamera` | 手机、笔记本内置摄像头、USB 摄像头 |
| `ZMQCamera` | 网络连接的摄像头 |
| `RealSenseCamera` | Intel RealSense（带深度信息） |
| `Reachy2Camera` | Reachy 2 机器人摄像头 |

> 有关 `OpenCVCamera` 的兼容性详情，请参阅 [OpenCV 视频 I/O 概述](https://docs.opencv.ac.cn/4.x/d0/da7/videoio_overview.html)。

### 查找您的摄像头

每个摄像头都需要一个唯一的标识符来实例化，以便您在多个连接的设备之间进行区分。

`OpenCVCamera` 和 `RealSenseCamera` 支持自动发现。运行以下命令以列出可用设备及其标识符。请注意，取决于您的操作系统，这些标识符在重启计算机或重新插拔摄像头后可能会发生变化。

```
lerobot-find-cameras opencv # or realsense for Intel Realsense cameras
```

如果您连接了两个摄像头，输出结果将类似于这样

```
--- Detected Cameras ---
Camera #0:
  Name: OpenCV Camera @ 0
  Type: OpenCV
  Id: 0
  Backend api: AVFOUNDATION
  Default stream profile:
    Format: 16.0
    Width: 1920
    Height: 1080
    Fps: 15.0
--------------------
(more cameras ...)
```

> 在 `macOS` 中使用 Intel RealSense 摄像头时，可能会遇到此 [错误](https://github.com/IntelRealSense/librealsense/issues/12307)：`Error finding RealSense cameras: failed to set power state`，这可以通过使用 `sudo` 权限运行相同命令来解决。请注意，在 `macOS` 中使用 RealSense 摄像头并不稳定。

`ZMQCamera` 和 `Reachy2Camera` 不支持自动发现。必须通过提供其网络地址和端口或机器人 SDK 设置来手动配置。

## 使用摄像头

### 帧访问模式

所有摄像头类都实现了三种用于捕获帧的访问模式

| 方法 | 行为 | 是否阻塞？ | 最适合 |
| --- | --- | --- | --- |
| `read()` | 等待摄像头硬件返回一帧。取决于摄像头和 SDK，可能会阻塞较长时间。 | 是 | 简单脚本、顺序采集 |
| `async_read(timeout_ms)` | 从后台线程返回最新的未消费帧。仅在缓冲区为空时阻塞，最长至 `timeout_ms`。如果没有帧到达，则抛出 `TimeoutError`。 | 带有超时时间 | 与摄像头 FPS 同步的控制循环 |
| `read_latest(max_age_ms)` | 查看缓冲区中最新的帧（可能是陈旧的）。如果帧的时间超过 `max_age_ms`，则抛出 `TimeoutError`。 | 否 | UI 可视化、日志记录、监控 |

### 使用示例

以下示例展示了如何使用摄像头 API 来配置并从不同类型的摄像头中捕获帧。

* 使用基于 OpenCV 的摄像头的**阻塞式和非阻塞式帧捕获**
* 使用 Intel RealSense 摄像头的**彩色和深度捕获**

> 未能干净地断开摄像头连接可能会导致资源泄漏。请使用上下文管理器协议以确保自动清理
>
> ```
> with OpenCVCamera(config) as camera:
>     ...
> ```
>
> 您也可以手动调用 `connect()` 和 `disconnect()`，但对于后者，请务必使用 `finally` 块。

Open CV 摄像头

Intel Realsense 摄像头

```
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot.cameras.opencv.camera_opencv import OpenCVCamera
from lerobot.cameras.configs import ColorMode, Cv2Rotation

# Construct an `OpenCVCameraConfig` with your desired FPS, resolution, color mode, and rotation.
config = OpenCVCameraConfig(
    index_or_path=0,
    fps=15,
    width=1920,
    height=1080,
    color_mode=ColorMode.RGB,
    rotation=Cv2Rotation.NO_ROTATION
)

# Instantiate and connect an `OpenCVCamera`, performing a warm-up read (default).
with OpenCVCamera(config) as camera:

    # Read a frame synchronously — blocks until hardware delivers a new frame
    frame = camera.read()
    print(f"read() call returned frame with shape:", frame.shape)

    # Read a frame asynchronously with a timeout — returns the latest unconsumed frame or waits up to timeout_ms for a new one
    try:
        for i in range(10):
            frame = camera.async_read(timeout_ms=200)
            print(f"async_read call returned frame {i} with shape:", frame.shape)
    except TimeoutError as e:
        print(f"No frame received within timeout: {e}")

    # Instantly return a frame - returns the most recent frame captured by the camera
    try:
        initial_frame = camera.read_latest(max_age_ms=1000)
        for i in range(10):
            frame = camera.read_latest(max_age_ms=1000)
            print(f"read_latest call returned frame {i} with shape:", frame.shape)
            print(f"Was a new frame received by the camera? {not (initial_frame == frame).any()}")
    except TimeoutError as e:
        print(f"Frame too old: {e}")
```

## 使用您的手机摄像头

iPhone & macOS

OBS 虚拟摄像头

要在 macOS 上将 iPhone 用作摄像头，请启用连续互通相机 (Continuity Camera) 功能

* 确保您的 Mac 运行的是 macOS 13 或更高版本，且您的 iPhone 运行的是 iOS 16 或更高版本。
* 使用相同的 Apple ID 登录这两个设备。
* 使用 USB 线连接设备，或开启 Wi-Fi 和蓝牙进行无线连接。

欲了解更多详情，请访问 [Apple 支持](https://support.apple.com/en-gb/guide/mac-help/mchl77879b8a/mac)。

如果一切设置正确，您的手机将显示为标准 OpenCV 摄像头，并可与 `OpenCVCamera` 配合使用。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/cameras.mdx)
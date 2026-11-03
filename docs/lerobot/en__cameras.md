# 来源

https://hugging-face.cn/docs/lerobot/en/cameras

# Cameras

LeRobot offers multiple options for video capture:

| Class | Supported Cameras |
| --- | --- |
| `OpenCVCamera` | Phone, built-in laptop, USB webcams |
| `ZMQCamera` | Network-connected cameras |
| `RealSenseCamera` | Intel RealSense (with depth) |
| `Reachy2Camera` | Reachy 2 robot cameras |

> For `OpenCVCamera` compatibility details, see the [Video I/O with OpenCV Overview](https://docs.opencv.org/4.x/d0/da7/videoio_overview.html).

### Find your camera

Every camera requires a unique identifier to be instantiated, allowing you to distinguish between multiple connected devices.

`OpenCVCamera` and `RealSenseCamera` support auto-discovery. Run the command below to list available devices and their identifiers. Note that these identifiers may change after rebooting your computer or re-plugging the camera, depending on your operating system.

```
lerobot-find-cameras opencv # or realsense for Intel Realsense cameras
```

The output will look something like this if you have two cameras connected:

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

> When using Intel RealSense cameras in `macOS`, you could get this [error](https://github.com/IntelRealSense/librealsense/issues/12307): `Error finding RealSense cameras: failed to set power state`, this can be solved by running the same command with `sudo` permissions. Note that using RealSense cameras in `macOS` is unstable.

`ZMQCamera` and `Reachy2Camera` do not support auto-discovery. They must be configured manually by providing their network address and port or robot SDK settings.

## Use cameras

 

### Frame access modes

All camera classes implement three access modes for capturing frames:

| Method | Behavior | Blocks? | Best For |
| --- | --- | --- | --- |
| `read()` | Waits for the camera hardware to return a frame. May block for a long time depending on the camera and SDK. | Yes | Simple scripts, sequential capture |
| `async_read(timeout_ms)` | Returns the latest unconsumed frame from background thread. Blocks only if buffer is empty, up to `timeout_ms`. Raises `TimeoutError` if no frame arrives. | With a timeout | Control loops synchronized to camera FPS |
| `read_latest(max_age_ms)` | Peeks at the most recent frame in buffer (may be stale). Raises `TimeoutError` if frame is older than `max_age_ms`. | No | UI visualization, logging, monitoring |

### Usage examples

The following examples show how to use the camera API to configure and capture frames from different camera types.

* **Blocking and non-blocking frame capture** using an OpenCV-based camera
* **Color and depth capture** using an Intel RealSense camera

> Failing to cleanly disconnect cameras can cause resource leaks. Use the context manager protocol to ensure automatic cleanup:
>
> ```
> with OpenCVCamera(config) as camera:
>     ...
> ```
>
> You can also call `connect()` and `disconnect()` manually, but always use a `finally` block for the latter.

Open CV Camera

Intel Realsense Camera

```
from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
from lerobot.cameras import ColorMode, Cv2Rotation

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

 

### Working with depth

The Intel RealSense and Reachy 2 cameras can capture both color and depth in lockstep. Calling `read()` returns the **color** frame as `(H, W, 3)` `uint8`. Calling `read_depth()` returns the **depth map** as `(H, W, 1)` `uint16`, where each pixel value is the distance from the sensor expressed in **millimetres**. A pixel value of `0` typically means “no measurement available” (out-of-range, occluded, or low-confidence).

During recording, the control loop peeks the freshest buffered frames non-blockingly via `read_latest()` (color) and `read_latest_depth()` (depth), adding the depth map as a sibling feature (e.g. `front_depth` next to `front`).

For how depth streams are stored and encoded when recording a dataset, see the [Depth streams](en__video_encoding_parameters.md#depth-streams) section of the video encoding guide.

## Use your phone’s camera

iPhone & macOS

OBS virtual camera

To use your iPhone as a camera on macOS, enable the Continuity Camera feature:

* Ensure your Mac is running macOS 13 or later, and your iPhone is on iOS 16 or later.
* Sign in both devices with the same Apple ID.
* Connect your devices with a USB cable or turn on Wi-Fi and Bluetooth for a wireless connection.

For more details, visit [Apple support](https://support.apple.com/en-gb/guide/mac-help/mchl77879b8a/mac).

If everything is set up correctly, your phone will appear as a standard OpenCV camera and can be used with `OpenCVCamera`.

 [Update on GitHub](https://github.com/huggingface/lerobot/blob/main/docs/source/cameras.mdx)
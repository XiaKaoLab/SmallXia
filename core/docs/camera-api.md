# 统一画面 API

Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian

服务地址 `http://127.0.0.1:8766`。以下路由均要求 `Authorization: Bearer <XIAOXIA_MOTION_TOKEN>`；POST 使用 JSON。令牌由现有桌面桥保管，不传入浏览器页面。

| 方法 | 路由 | 功能 |
| --- | --- | --- |
| POST | `/api/v1/cameras/virtual/frame` | table 上传 JPEG，参数 `image_base64`，最大 1 MB、最长边 1920 像素 |
| GET | `/api/v1/cameras/virtual/frame` | 获取最新虚拟画面；超过 2 秒未收到新帧返回 409 |
| POST | `/api/v1/cameras/real/config` | `{"device_index":0,"enabled":true}` 连接本机 OpenCV 设备；`enabled:false` 释放设备 |
| GET | `/api/v1/cameras/real/frame` | 读取并编码真实相机画面；未连接或读取失败返回错误 |

响应包含 `source`（virtual/real）、`physical`、`sequence`、`timestamp_ns`、`timestamp_basis`、`age_ms`、`width`、`height`、`encoding:jpeg`、`image_base64`。时间戳为 core 收到/读取图像后的主机时间，不是传感器曝光时间，不保证与关节观测同步。真实图像经 OpenCV 从 BGR 编码，Python RGB 解码函数统一返回 RGB 数组。

虚拟画面来自装配相机后的独立渲染画布，最多 2 FPS 上传，采用丢帧而非排队；必须保持 Tauri table 窗口和 core 服务运行。不显示相机时停止上传。当前不作为高帧率训练采集链路或 LeRobot Camera 子类注册。

积木“相机”分类提供“获取画面”，“变量”分类提供“画面变量”，来源可选虚拟/真实。先运行获取积木，再使用对应变量。两种来源各自保存为 `virtual_frame`、`real_frame`。变量是包含图像和元数据的字典；不是图像路径或 WebView 截图。Python 不显示在界面中。

```python
from xiaoxia_core.collection.frame_client import CameraFrameClient

camera = CameraFrameClient()
virtual_frame = camera.read("virtual")
rgb = camera.rgb(virtual_frame)  # H×W×3 uint8 RGB

# 仅在明确需要读取本机设备时调用；不枚举、不自动开启。
camera.configure_real(device_index=0)
try:
    real_frame = camera.read("real")
    real_rgb = camera.rgb(real_frame)
finally:
    camera.configure_real(enabled=False)
```

真实相机依赖现有 base 环境中的 OpenCV；服务退出时释放设备。修改模型服务代码后需重启该 Python 服务，桌面前端使用 HMR。

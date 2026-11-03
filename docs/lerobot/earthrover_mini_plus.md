# 来源

https://hugging-face.cn/docs/lerobot/earthrover_mini_plus

# EarthRover Mini Plus

![EarthRover Mini Plus](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/Earth_Rover_Mini_5_240c9adc-4f9e-44b7-982f-5d1dc24af1d8.png.webp)

EarthRover Mini Plus 是一款完全开源的移动机器人，它使用 Frodobots SDK 通过云端进行连接。这使您可以控制机器人并记录数据集以训练 AI 模型。

## 所需准备

### 硬件

* EarthRover Mini 机器人
* 安装有 Python 3.12 或更高版本的电脑
* 互联网连接

### 设置 Frodobots SDK

机器人需要电脑上运行 [Frodobots SDK](https://github.com/frodobots-org/earth-rovers-sdk)。操作步骤如下：

1. 下载并安装 SDK

```
git clone https://github.com/frodobots-org/earth-rovers-sdk.git
cd earth-rovers-sdk
pip install -r requirements.txt
```

2. 保存凭证

使用 Frodobots 团队提供的 SDK API 密钥和机器人名称编写您的 .env 变量。

```
SDK_API_TOKEN=your_sdk_api_token_here
BOT_SLUG=your_bot_slug_here
CHROME_EXECUTABLE_PATH=/path/to/chrome_or_chromium
# Default value is MAP_ZOOM_LEVEL=18 https://wiki.openstreetmap.org/wiki/Zoom_levels
MAP_ZOOM_LEVEL=18
MISSION_SLUG=your_mission_slug_here
# Image quality between 0.1 and 1.0 (default: 0.8)
# Recommended: 0.8 for better performance
IMAGE_QUALITY=0.8
# Image format: jpeg, png or webp (default: png)
# Recommended: jpeg for better performance and lower bandwidth usage
IMAGE_FORMAT=jpeg
```

3. 启动 SDK

```
hypercorn main:app --reload
```

4. 打开浏览器并访问 `https://:8000`，然后点击“Join”（加入）

SDK 将为您提供：

* 来自前后摄像头的实时视频

> 在使用机器人之前，必须先运行 SDK。

## 安装 LeRobot

按照我们的 [安装指南](installation.md) 来安装 LeRobot。

除了基础安装外，还需要安装 EarthRover Mini 的依赖项

```
pip install -e .
```

## 工作原理

机器人利用互联网进行通信

* **移动指令**：通过 SDK 发送
* **摄像头视频**：从 SDK 接收
* **机器人信息**：从 SDK 获取电池、位置、速度等信息

您无需插入任何线缆——一切都通过 SDK 完成。

## 校准

无需校准！SDK 运行后机器人即可直接使用。

## 控制机器人

您可以使用键盘控制机器人——就像玩视频游戏时使用 WASD 键一样。

### 键盘控制

| 键 | 行动 |
| --- | --- |
| W | 向前移动 |
| S | 向后移动 |
| A | 左转（前进时） |
| D | 右转（前进时） |
| Q | 原地左转 |
| E | 原地右转 |
| X | 停止所有移动 |
| +/= | 增加速度 |
| - | 降低速度 |
| ESC | 断开连接 |

### 速度设置

您可以调整机器人的移动速度

* **前进/后退速度**：默认为全速 (1.0)
* **转向速度**：默认为全速 (1.0)
* **速度调整**：使用 +/- 键，每次调整 0.1

### 试运行

在记录数据之前先进行试驾

```
from lerobot.robots.earthrover_mini_plus import EarthRoverMiniPlus, EarthRoverMiniPlusConfig
from lerobot.teleoperators.keyboard import KeyboardRoverTeleop, KeyboardRoverTeleopConfig

# Initialize robot
robot_config = EarthRoverMiniPlusConfig()
robot = EarthRoverMiniPlus(robot_config)

# Initialize teleoperator
teleop_config = KeyboardRoverTeleopConfig(
    linear_speed=1.0,
    angular_speed=1.0,
    speed_increment=0.1
)
teleop = KeyboardRoverTeleop(teleop_config)

# Connect
robot.connect()
teleop.connect()

# Teleoperate (use keyboard controls)
try:
    while True:
        action = teleop.get_action()
        robot.send_action(action)
except KeyboardInterrupt:
    pass
finally:
    robot.disconnect()
    teleop.disconnect()
```

> 如果您使用 Mac，可能需要授予终端（Terminal）访问键盘的权限，以便进行远程操作。请前往“系统偏好设置”>“安全性与隐私”>“输入监控”，并勾选终端选项。

## 记录数据

一旦您可以熟练驾驶机器人，就可以开始记录数据以训练 AI 模型。系统会记录：

* **您的操作**：您如何移动机器人（前进、后退、转向）
* **机器人的观测数据**:
  + 来自两个摄像头的视频
  + 机器人的速度和方向
  + 电池电量和位置
  + GPS 位置和信号
  + 其他传感器数据
* **发生时间**：所有数据的精确时间戳

### 设置 Hugging Face

我们使用 Hugging Face 在线存储您的数据。首先，使用来自 [Hugging Face 设置](https://hugging-face.cn/settings/tokens) 的令牌登录。

```
hf auth login --token ${HUGGINGFACE_TOKEN} --add-to-git-credential
```

保存您的 Hugging Face 用户名

```
HF_USER=$(hf auth whoami | awk -F': *' 'NR==1 {print $2}')
echo $HF_USER
```

### 开始录制

使用标准的录制命令

```
lerobot-record \
    --robot.type=earthrover_mini_plus \
    --teleop.type=keyboard_rover \
    --dataset.repo_id=your_username/dataset_name \
    --dataset.num_episodes=2 \
    --dataset.fps=10 \
    --dataset.single_task="Navigate around obstacles" \
    --dataset.streaming_encoding=true \
    --dataset.encoder_threads=2 \
    # --dataset.vcodec=auto \
    --display_data=true
```

将 `your_username/dataset_name` 替换为您的 Hugging Face 用户名和数据集名称。

### 保存内容

您的数据集包括

**您的操作（2 个特征）**:

* `linear_velocity`：前进/后退的位移量
* `angular_velocity`：左转/右转的转向量

**机器人观测数据（24 个特征）**:

* 前置摄像头视频
* 后置摄像头视频
* 当前速度
* 电池电量
* 朝向
* GPS（经度、纬度、信号强度）
* 网络信号强度
* 振动水平
* 灯光状态（开/关）
* 加速度计 (x, y, z)
* 陀螺仪 (x, y, z)
* 磁力计 (x, y, z)
* 车轮 RPM（4 个轮子）

### 数据存储位置

在您的计算机上：`~/.cache/huggingface/lerobot/{repo-id}`

记录完成后，您的数据会自动上传至您的 Hugging Face 页面

```
echo https://hugging-face.cn/datasets/${HF_USER}/earthrover-navigation
```

您的数据集将被标记为 `LeRobot`，以便社区发现。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/earthrover_mini_plus.mdx)
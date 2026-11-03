# 来源

https://hugging-face.cn/docs/lerobot/lekiwi

# LeKiwi

![LeKiwi](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/1740517739083.jpeg)

在以下步骤中，我们将说明如何组装 LeKiwi 移动机器人。

## 采购零件

请遵循这份 [README](https://github.com/SIGRobotics-UIUC/LeKiwi)。它包含了物料清单、零件采购链接以及 3D 打印零件的说明。如果您是第一次打印或没有 3D 打印机，它也会提供相关建议。

### 有线版本

如果您拥有 **有线** 版本的 LeKiwi，可以跳过安装 Raspberry Pi 和设置 SSH 的步骤。您可以直接在电脑上运行 LeKiwi 脚本和用于远程操控的主控制臂脚本。

## 在 Pi 上安装软件

现在我们需要设置将运行在 LeKiwi 机器人上的远程 PC。这通常是 Raspberry Pi，但也可以是任何能以 5V 运行并具有足够 USB 端口（2 个或更多）供摄像头和电机控制板使用的 PC。

### 安装操作系统

有关 Raspberry Pi 及其 SD 卡的设置，请参阅：[设置 Pi](https://www.raspberrypi.com/documentation/computers/getting-started.html)。这里解释了如何下载 [Imager](https://www.raspberrypi.com/software/) 来安装 Raspberry Pi OS 或 Ubuntu。

### 设置 SSH

设置好 Pi 后，您应该启用并设置 [SSH](https://www.raspberrypi.com/news/coding-on-raspberry-pi-remotely-with-visual-studio-code/)（安全外壳协议），这样您就可以从笔记本电脑登录到 Pi，而不需要在 Pi 上连接屏幕、键盘和鼠标。有关如何执行此操作的一个很好的教程可以在[这里](https://www.raspberrypi.com/documentation/computers/remote-access.html#ssh)找到。您可以在命令提示符 (cmd) 中登录 Pi，或者如果您使用 VSCode，可以使用[此](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh)扩展插件。

### 在 Pi 上安装 LeRobot 🤗

参考我们的 [安装指南](installation.md) 在您的 Raspberry Pi 上安装 LeRobot。

除了这些说明外，您还需要在 Pi 上安装 Feetech SDK 和 ZeroMQ。

```
pip install -e ".[lekiwi]"
```

## 在本地安装 LeRobot

如果您已经在笔记本电脑/电脑上安装了 LeRobot，可以跳过此步骤；否则，请按照我们在 Pi 上执行的相同步骤进行操作。

遵循我们的 [安装指南](installation.md)

除了这些说明外，您还需要在笔记本电脑/电脑上安装 Feetech SDK 和 ZeroMQ。

```
pip install -e ".[lekiwi]"
```

太棒了 :hugs:！您现在已完成 LeRobot 的安装，我们可以开始组装 SO100/SO101 机械臂和移动底座 :robot:。之后每次您想使用 LeRobot 时，都可以进入安装 LeRobot 的 `~/lerobot` 文件夹并运行其中一个命令。

# 逐步组装说明

首先，我们将组装两个 SO100/SO101 机械臂。一个安装在移动底座上，一个用于远程操控。然后我们将组装移动底座。组装说明可以在这两个页面上找到：

* [组装 SO101](so101.md#step-by-step-assembly-instructions)
* [组装 LeKiwi](https://github.com/SIGRobotics-UIUC/LeKiwi/blob/main/Assembly.md)

### 查找电机板关联的 USB 端口

要查找每个总线伺服适配器的端口，请运行此脚本

```
lerobot-find-port
```

Mac

Linux

示例输出

```
Finding all available ports for the MotorBus.
['/dev/tty.usbmodem575E0032081']
Remove the USB cable from your MotorsBus and press Enter when done.

[...Disconnect corresponding leader or follower arm and press Enter...]

The port of this MotorsBus is /dev/tty.usbmodem575E0032081
Reconnect the USB cable.
```

其中找到的端口为：`/dev/tty.usbmodem575E0032081`，对应于您的电路板。

### 配置电机

配置电机的说明可以在 SO101 [文档](so101.md#configure-the-motors) 中找到。除了机械臂电机的 ID 外，我们还需要设置移动底座的电机 ID。这些必须按特定顺序排列才能工作。下图显示了移动底座的电机 ID 和电机安装位置。请注意，LeKiwi 上我们只使用一个电机控制板。这意味着轮子的电机 ID 为 7、8 和 9。

您可以运行此命令来设置 LeKiwi 的电机。它将首先设置机械臂的电机（ID 6..1），然后设置轮子的电机（9,8,7）。

```
lerobot-setup-motors \
    --robot.type=lekiwi \
    --robot.port=/dev/tty.usbmodem58760431551 # <- paste here the port found at previous step
```

![Motor ID's for mobile robot](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/motor_ids.webp "Motor ID's for mobile robot")

### 排查通信故障

如果您在连接移动版 SO100 时遇到困难，请按照以下步骤诊断并解决问题。

#### 1. 验证 IP 地址配置

确保在命令或代码中使用了正确的 Pi IP。要检查 Raspberry Pi 的 IP 地址，请运行（在 Pi 命令行中）：

```
hostname -I
```

#### 2. 检查 Pi 是否可从笔记本电脑/电脑访问

尝试从笔记本电脑 ping Raspberry Pi。

```
ping <your_pi_ip_address>
```

如果 ping 失败：

* 确保 Pi 已开机并连接到同一个网络。
* 检查 Pi 上是否已启用 SSH。

#### 3. 尝试 SSH 连接

如果您无法通过 SSH 进入 Pi，可能是它未正确连接。使用：

```
ssh <your_pi_user_name>@<your_pi_ip_address>
```

如果您收到连接错误：

* 通过运行以下命令确保 Pi 上启用了 SSH：

  ```
  sudo raspi-config
  ```

  然后导航到：**Interfacing Options -> SSH** 并启用它。

### 校准

现在我们必须校准主控制臂和从机械臂。轮子电机不需要校准。校准过程非常重要，因为它允许在某个机器人上训练的神经网络也能在另一个机器人上运行。

### 校准从机械臂（移动底座上的）

确保机械臂已连接到 Raspberry Pi，并运行此脚本或 API 示例（通过 SSH 在 Raspberry Pi 上运行）以启动从机械臂的校准：

```
lerobot-calibrate \
    --robot.type=lekiwi \
    --robot.id=my_awesome_kiwi # <- Give the robot a unique name
```

我们为大多数机器人统一了校准方法，因此 SO100 机械臂的校准步骤与 Koch 和 SO101 的步骤相同。首先，我们必须将机器人移动到每个关节都处于其运动范围中间的位置，然后按下 `Enter`。其次，我们将所有关节移动过其整个运动范围。可参考[此处](en__so101.md#calibration-video) SO101 相同校准过程的视频。

### 有线版本

如果您拥有 **有线** LeKiwi 版本，请在笔记本电脑上运行所有命令。

### 校准主控制臂

然后，校准连接到笔记本电脑/电脑的主控制臂。在笔记本电脑上运行以下 API 示例命令：

命令

API 示例

```
lerobot-calibrate \
    --teleop.type=so100_leader \
    --teleop.port=/dev/tty.usbmodem58760431551 \ # <- The port of your robot
    --teleop.id=my_awesome_leader_arm # <- Give the robot a unique name
```

## 遥操作 LeKiwi

> 如果您使用的是 Mac，可能需要授予终端权限才能访问您的键盘进行遥操作。前往“系统偏好设置” > “安全性与隐私” > “输入监听”，并勾选“终端”。

要进行遥操作，请通过 SSH 进入您的 Raspberry Pi，运行 `conda activate lerobot`，然后执行此命令：

```
python -m lerobot.robots.lekiwi.lekiwi_host --robot.id=my_awesome_kiwi
```

然后在笔记本电脑上，同样运行 `conda activate lerobot` 并运行 API 示例，确保在 `examples/lekiwi/teleoperate.py` 中设置了正确的 `remote_ip` 和 `port`。

```
python examples/lekiwi/teleoperate.py
```

您应该在笔记本电脑上看到类似以下内容：`[INFO] Connected to remote robot at tcp://172.17.133.91:5555 and video stream at tcp://172.17.133.91:5556.` 现在您可以移动主控制臂，并使用键盘 (w,a,s,d) 控制机器人前进、向左、后退、向右。使用 (z,x) 进行左转或右转。您可以使用 (r,f) 来增加或降低移动机器人的速度。有三种速度模式，详见下表：

| 速度模式 | 线速度 (m/s) | 旋转速度 (deg/s) |
| --- | --- | --- |
| 快 | 0.4 | 90 |
| 中型 | 0.25 | 60 |
| 慢速 | 0.1 | 30 |

| 键 | 行动 |
| --- | --- |
| W | 前进 |
| A | 向左平移 |
| S | 后退 |
| D | 向右平移 |
| Z | 左转 |
| X | 右转 |
| R | 加速 |
| F | 减速 |

> 如果您使用不同的键盘，可以在 [`LeKiwiClientConfig`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/robots/lekiwi/config_lekiwi.py) 中更改每个命令对应的按键。

### 有线版本

如果您拥有 **有线** LeKiwi 版本，请在笔记本电脑上运行所有命令。

## 录制数据集

一旦您熟悉了远程操作，您就可以记录您的第一个数据集。

我们使用 Hugging Face Hub 的功能来上传您的数据集。如果您以前没有使用过 Hub，请确保您可以通过 cli 使用具有“写入权限”的令牌登录，该令牌可以从 [Hugging Face 设置](https://hugging-face.cn/settings/tokens) 中生成。

通过运行此命令将您的令牌添加到 CLI

```
hf auth login --token ${HUGGINGFACE_TOKEN} --add-to-git-credential
```

然后将您的 Hugging Face 存储库名称存储在一个变量中

```
HF_USER=$(hf auth whoami | awk -F': *' 'NR==1 {print $2}')
echo $HF_USER
```

现在您可以录制数据集了。要录制回合（episodes）并将数据集上传到 Hub，请执行此为 LeKiwi 量身定制的 API 示例。请务必先修改脚本中的 `remote_ip`、`repo_id`、`port` 和 `task`。如果您想运行更长时间，可以增大 `NB_CYCLES_CLIENT_CONNECTION`。

```
python examples/lekiwi/record.py
```

#### 上传数据集

在本地，您的高级数据集存储在以下文件夹中：`~/.cache/huggingface/lerobot/{repo-id}`。数据录制结束时，您的高级数据集将上传到您的 Hugging Face 页面（例如 <https://hugging-face.cn/datasets/cadene/so101_test>），您可以通过运行以下命令获取该数据集：

```
echo https://hugging-face.cn/datasets/${HF_USER}/so101_test
```

您的数据集将自动标记为 `LeRobot`，以便社区轻松找到它，您还可以添加自定义标签（例如，在此示例中为 `tutorial`）。

您可以通过搜索 `LeRobot` [标签](https://hugging-face.cn/datasets?other=LeRobot)在 Hub 上查找其他 LeRobot 数据集。

#### 数据收集技巧

一旦您熟悉了数据录制，就可以创建一个更大的数据集进行训练。一个很好的入门任务是在不同位置抓取物体并将其放入箱子中。我们建议录制至少 50 个回合，每个位置录制 10 个回合。保持摄像头固定，并在整个录制过程中保持抓取行为的一致性。同时确保您操作的物体在摄像头中可见。一个简单的经验法则是，您应该能够仅通过观看摄像头图像就能自己完成任务。

在接下来的部分中，您将训练您的神经网络。在获得可靠的抓取性能后，您可以在数据收集期间开始引入更多变化，例如增加抓取位置、尝试不同的抓取技术以及更改摄像头位置。

避免过快地添加太多变化，因为它可能会阻碍您的结果。

如果您想深入了解这个重要主题，您可以查看我们撰写的关于什么是一个好的数据集的[博客文章](https://hugging-face.cn/blog/lerobot-datasets#what-makes-a-good-dataset)。

#### 故障排除：

* 在 Linux 上，如果左右箭头键和 ESC 键在数据录制期间没有任何反应，请确保您已设置了 `$DISPLAY` 环境变量。请参阅 [pynput 的局限性](https://pynput.readthedocs.io/en/latest/limitations.html#linux)。

## 回放回合

要回放一个回合，请运行下面的 API 示例，请务必更改 `remote_ip`、`port`、LeRobotDatasetId 和 episode index（回合索引）。

```
python examples/lekiwi/replay.py
```

恭喜 🎉，您的机器人已准备就绪，可以自主学习任务了。通过本教程的训练部分开始训练它：[真实世界机器人入门指南](il_robots.md)

## 评估您的策略

要评估您的策略，请运行 `evaluate.py` API 示例，请务必更改 `remote_ip`、`port`、model（模型）等...

```
python examples/lekiwi/evaluate.py
```

> 如果你有任何问题或需要帮助，请在 [Discord](https://discord.com/invite/s3KuuzsPFb) 上联系我们。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/lekiwi.mdx)
# 来源

https://hugging-face.cn/docs/lerobot/koch

# Koch v1.1

在下面的步骤中，我们将说明如何组装 Koch v1.1 机器人。

## 订购并组装零件

请遵循此 [README](https://github.com/jess-moss/koch-v1-1) 中提供的采购和组装说明。它将引导您完成从动臂和主动臂的设置，如下图所示。

有关组装过程的可视化演练，您可以参考[此视频教程](https://youtu.be/8nQIg9BwwTk)。

> 自该视频制作以来，我们简化了配置阶段。因此，有两点与该视频中的说明不同
>
> * 不要立即插上所有电机电缆，请等待 [配置电机](koch.md#configure-the-motors) 中的指示。
> * 不要立即将控制板 (PCB) 拧到底座上，请等待 [配置电机](koch.md#configure-the-motors) 中的指示。

## 安装 LeRobot 🤗

要安装 LeRobot，请遵循我们的 [安装指南](installation.md)

除这些说明外，您还需要安装 Dynamixel SDK

```
pip install -e ".[dynamixel]"
```

## 配置电机

### 1. 查找每个机械臂对应的 USB 端口

要查找每个总线伺服适配器的端口，请运行此脚本

```
lerobot-find-port
```

Mac

Linux

示例输出

```
Finding all available ports for the MotorBus.
['/dev/tty.usbmodem575E0032081', '/dev/tty.usbmodem575E0031751']
Remove the USB cable from your MotorsBus and press Enter when done.

[...Disconnect corresponding leader or follower arm and press Enter...]

The port of this MotorsBus is /dev/tty.usbmodem575E0032081
Reconnect the USB cable.
```

找到的端口是： `/dev/tty.usbmodem575E0032081`，对应于您的主控臂或从动臂。

### 2. 设置电机的 ID 和波特率

每个电机在总线上都有唯一的 ID。当电机是全新的时，它们的默认 ID 通常是`1`。为了让电机和控制器之间正常通信，我们需要为每个电机设置一个唯一的、不同的 ID。此外，总线上数据传输的速度由波特率决定。为了相互通信，控制器和所有电机都需要配置相同的波特率。

为此，我们首先需要单独连接每个电机和控制器来设置这些参数。由于我们会将这些参数写入电机内部存储器的非易失性部分（EEPROM），所以我们只需要做一次。

如果您是从另一个机器人上重新利用电机，您可能也需要执行此步骤，因为 ID 和波特率可能不匹配。

#### 跟随者

将计算机的 USB 线和 5V 电源连接到从动臂的控制板上。然后，运行以下命令，或使用上一步中获取的端口运行 API 示例。您还需要使用 `id` 参数为您的主动臂指定一个名称。

有关如何设置电机 ID 的视觉参考，请参考[此视频](en__so101.md#setup-motors-video)，我们在其中演示了 SO101 机械臂的处理过程。

命令

API 示例

```
lerobot-setup-motors \
    --robot.type=koch_follower \
    --robot.port=/dev/tty.usbmodem575E0031751 # <- paste here the port found at previous step
```

您应该会看到以下说明。

```
Connect the controller board to the 'gripper' motor only and press enter.
```

按照指示，连接夹爪电机。请确保它是唯一连接到板上的电机，并且电机本身尚未与其他电机级联。当您按下 `[Enter]` 时，脚本将自动为该电机设置 ID 和波特率。

故障排除

如果此时出现错误，请检查您的电缆并确保它们已正确插入。

* 电源
* 电脑和控制器板之间的 USB 电缆
* 从控制器板到电机的 3 针电缆

如果您使用的是 Waveshare 控制器板，请确保两个跳线都设置在 `B` 通道（USB）上。

然后您应该看到以下消息

```
'gripper' motor id set to 6
```

接着是下一条指令

```
Connect the controller board to the 'wrist_roll' motor only and press enter.
```

您可以从控制板上拔下 3 针电缆，但可以保持另一端连接到夹持器电机上，因为它已经处于正确位置。现在，将另一根 3 针电缆插到手腕翻转电机上，并将其连接到控制板。与之前的电机一样，请确保它是唯一连接到板上的电机，并且电机本身没有连接到任何其他电机。

按照指示为每个电机重复此操作。

> 在按 Enter 键之前，请在每一步检查您的布线。例如，在操作电路板时，电源线可能会断开。

完成后，脚本将自动完成，此时电机就可以使用了。现在您可以将每个电机的三线电缆连接到下一个电机，并将第一根电机（ID=1 的“肩部旋转”）的电缆连接到控制器板，控制器板现在可以安装在机械臂的底部。

#### 领导者

对主动臂执行相同的步骤，但相应地修改命令或脚本。

命令

API 示例

```
lerobot-setup-motors \
    --teleop.type=koch_leader \
    --teleop.port=/dev/tty.usbmodem575E0031751 \  # <- paste here the port found at previous step
```

## 校准

接下来，您需要校准机器人，以确保领导者和跟随者机械臂在物理位置相同时具有相同的姿态值。校准过程非常重要，因为它允许在一个机器人上训练的神经网络在另一个机器人上也能正常工作。

#### 跟随者

运行以下命令或 API 示例来校准从动臂

命令

API 示例

```
lerobot-calibrate \
    --robot.type=koch_follower \
    --robot.port=/dev/tty.usbmodem58760431551 \ # <- The port of your robot
    --robot.id=my_awesome_follower_arm  # <- Give the robot a unique name
```

我们统一了大多数机械臂的校准方法。因此，Koch 机械臂的校准步骤与 SO100 和 SO101 的步骤相同。首先，我们必须将机器人移动到每个关节都处于其量程中间的位置，然后按 `Enter`。其次，我们将所有关节移动到其完整的运动范围内。SO101 相同过程的参考视频可以在[这里](en__so101.md#calibration-video)找到。

#### 领导者

执行相同的步骤来校准主控臂，运行以下命令或 API 示例

命令

API 示例

```
lerobot-calibrate \
    --teleop.type=koch_leader \
    --teleop.port=/dev/tty.usbmodem58760431551 \ # <- The port of your robot
    --teleop.id=my_awesome_leader_arm  # <- Give the robot a unique name
```

恭喜 🎉，您的机器人已准备好自主学习任务。请遵循本教程开始训练它：[真实世界机器人入门](il_robots.md)

> 如果你有任何问题或需要帮助，请在 [Discord](https://discord.com/invite/s3KuuzsPFb) 上联系我们。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/koch.mdx)
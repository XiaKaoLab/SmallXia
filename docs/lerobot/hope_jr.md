# 来源

https://hugging-face.cn/docs/lerobot/hope_jr

# HopeJR

## 先决条件

* [硬件设置](https://github.com/TheRobotStudio/HOPEJr)

## 安装 LeRobot

按照 [安装说明](https://github.com/huggingface/lerobot#installation) 安装 LeRobot。

安装带有 HopeJR 依赖项的 LeRobot

```
pip install -e ".[hopejr]"
```

## 设备配置

在开始校准和操作之前，您需要识别每个 HopeJR 组件的 USB 端口。运行此脚本以查找机械臂、手部、手套和外骨骼的 USB 端口

```
lerobot-find-port
```

这将显示可用的 USB 端口及其关联设备。请记录端口路径（例如 `/dev/tty.usbmodem58760433331`，`/dev/tty.usbmodem11301`），因为在记录数据、回放片段或运行遥操作脚本时，您需要在 `--robot.port` 和 `--teleop.port` 参数中指定它们。

## 步骤 1：校准

在进行遥操作之前，需要对 HopeJR 的肢体进行校准。校准文件将保存在 `~/.cache/huggingface/lerobot/calibration`

### 1.1 校准机器人手

```
lerobot-calibrate \
    --robot.type=hope_jr_hand \
    --robot.port=/dev/tty.usbmodem58760432281 \
    --robot.id=blue \
    --robot.side=right
```

运行校准脚本时，会弹出校准 GUI。手指关节命名如下

**拇指**:

* **CMC**：连接拇指与手部的基关节
* **MCP**：指关节
* **PIP**：第一指间关节
* **DIP** ：指尖关节

**食指、中指、无名指和小指**:

* **桡侧屈肌 (Radial flexor)**：将手指基部向拇指方向移动
* **尺侧屈肌 (Ulnar flexor)**：将手指基部向小指方向移动
* **PIP/DIP**：弯曲手指的远端和近端指节

其中的每一个都需要通过 GUI 单独校准。请注意，尺侧和桡侧屈肌应具有相同大小的范围（但偏移量不同），以获得对称运动。

![Setting boundaries in the hand calibration GUI](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/calibration_gui_1.png "Setting boundaries in the hand calibration GUI")

使用校准界面为每个关节设置如上所示的范围边界。

![Saving calibration values](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/calibration_gui_2.png "Saving calibration values")

为所有关节设置好合适的边界后，点击 “Save” 以将校准值保存到电机。

### 1.2 校准遥操作手套

```
lerobot-calibrate \
    --teleop.type=homunculus_glove \
    --teleop.port=/dev/tty.usbmodem11201 \
    --teleop.id=red \
    --teleop.side=right
```

从拇指开始，移动每根手指使其达到全范围活动。

```
Move thumb through its entire range of motion.
Recording positions. Press ENTER to stop...

-------------------------------------------
NAME      |    MIN |    POS |    MAX
thumb_cmc |   1790 |   1831 |   1853
thumb_mcp |   1497 |   1514 |   1528
thumb_pip |   1466 |   1496 |   1515
thumb_dip |   1463 |   1484 |   1514
```

对每根手指继续此操作

```
Move middle through its entire range of motion.
Recording positions. Press ENTER to stop...

-------------------------------------------
NAME                 |    MIN |    POS |    MAX
middle_mcp_abduction |   1598 |   1718 |   1820
middle_mcp_flexion   |   1512 |   1658 |   2136
middle_dip           |   1484 |   1500 |   1547
```

校准完成后，系统会将校准结果保存到 `/Users/your_username/.cache/huggingface/lerobot/calibration/teleoperators/homunculus_glove/red.json`

### 1.3 校准机器人臂

```
lerobot-calibrate \
    --robot.type=hope_jr_arm \
    --robot.port=/dev/tty.usbserial-1110 \
    --robot.id=white
```

这将打开一个校准 GUI，您可以在其中设置每个电机的范围限制。机械臂动作组织如下

* **肩部**：俯仰 (pitch)、偏航 (yaw) 和横滚 (roll)
* **肘部**：屈曲 (flex)
* **腕部**：俯仰 (pitch)、偏航 (yaw) 和横滚 (roll)

![Setting boundaries in the arm calibration GUI](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/calibration_gui_2.png "Setting boundaries in the arm calibration GUI")

使用校准界面设置每个关节的范围边界。使每个关节在全活动范围内运动，并相应调整最小值和最大值。为所有关节设置好适当的边界后，保存校准。

### 1.4 校准遥操作外骨骼

```
lerobot-calibrate \
    --teleop.type=homunculus_arm \
    --teleop.port=/dev/tty.usbmodem11201 \
    --teleop.id=black
```

外骨骼允许用户控制机器人臂。在校准过程中，系统会提示您将所有关节移动到其全活动范围

```
Move all joints through their entire range of motion.
Recording positions. Press ENTER to stop...

-------------------------------------------
-------------------------------------------
NAME            |    MIN |    POS |    MAX
shoulder_pitch  |    586 |    736 |    895
shoulder_yaw    |   1257 |   1374 |   1390
shoulder_roll   |    449 |   1034 |   2564
elbow_flex      |   3023 |   3117 |   3134
wrist_roll      |   3073 |   3096 |   3147
wrist_yaw       |   2143 |   2171 |   2185
wrist_pitch     |   1975 |   1993 |   2074
Calibration saved to /Users/your_username/.cache/huggingface/lerobot/calibration/teleoperators/homunculus_arm/black.json
```

## 步骤 2：遥操作

由于 Feetech 中间件中的全局变量冲突，机械臂和手部的遥操作必须在独立的 shell 会话中运行

### 手部

```
lerobot-teleoperate \
    --robot.type=hope_jr_hand \
    --robot.port=/dev/tty.usbmodem58760432281 \
    --robot.id=blue \
    --robot.side=right \
    --teleop.type=homunculus_glove \
    --teleop.port=/dev/tty.usbmodem11201 \
    --teleop.id=red \
    --teleop.side=right \
    --display_data=true \
    --fps=30
```

### 机械臂

```
lerobot-teleoperate \
    --robot.type=hope_jr_arm \
    --robot.port=/dev/tty.usbserial-1110 \
    --robot.id=white \
    --teleop.type=homunculus_arm \
    --teleop.port=/dev/tty.usbmodem11201 \
    --teleop.id=black \
    --display_data=true \
    --fps=30
```

## 步骤 3：记录、回放、训练

使用 Hope-JR 进行记录、回放和训练仍处于实验阶段。

### 记录

此步骤记录数据集，示例请参见[此处](https://hugging-face.cn/datasets/nepyope/hand_record_test_with_video_data/settings)。

```
lerobot-record \
    --robot.type=hope_jr_hand \
    --robot.port=/dev/tty.usbmodem58760432281 \
    --robot.id=right \
    --robot.side=right \
    --robot.cameras='{"main": {"type": "opencv", "index_or_path": 0, "width": 640, "height": 480, "fps": 30}}' \
    --teleop.type=homunculus_glove \
    --teleop.port=/dev/tty.usbmodem1201 \
    --teleop.id=right \
    --teleop.side=right \
    --dataset.repo_id=<USER>/hand_record_test_with_video_data \
    --dataset.single_task="Hand recording test with video data" \
    --dataset.num_episodes=1 \
    --dataset.episode_time_s=5 \
    --dataset.push_to_hub=true \
    --dataset.private=true \
    --dataset.streaming_encoding=true \
    --dataset.encoder_threads=2 \
    # --dataset.vcodec=auto \
    --display_data=true
```

### 回放

```
lerobot-replay \
    --robot.type=hope_jr_hand \
    --robot.port=/dev/tty.usbmodem58760432281 \
    --robot.id=right \
    --robot.side=right \
    --dataset.repo_id=<USER>/hand_record_test_with_camera \
    --dataset.episode=0
```

### 训练

```
lerobot-train \
  --dataset.repo_id=<USER>/hand_record_test_with_video_data \
  --policy.type=act \
  --output_dir=outputs/train/hopejr_hand \
  --job_name=hopejr \
  --policy.device=mps \
  --wandb.enable=true \
  --policy.repo_id=<USER>/hand_test_policy
```

### 评估

此次训练运行示例请参见[此处](https://wandb.ai/tino/lerobot/runs/rp0k8zvw?nw=nwusertino)。

```
lerobot-record \
  --robot.type=hope_jr_hand \
  --robot.port=/dev/tty.usbmodem58760432281 \
  --robot.id=right \
  --robot.side=right \
  --robot.cameras='{"main": {"type": "opencv", "index_or_path": 0, "width": 640, "height": 480, "fps": 30}}' \
  --display_data=false \
  --dataset.repo_id=<USER>/eval_hopejr \
  --dataset.single_task="Evaluate hopejr hand policy" \
  --dataset.num_episodes=10 \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2 \
  # --dataset.vcodec=auto \
  --policy.path=outputs/train/hopejr_hand/checkpoints/last/pretrained_model
```

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/hope_jr.mdx)
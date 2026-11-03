# 来源

https://hugging-face.cn/docs/lerobot/il_robots

# 真实世界机器人上的模仿学习

本教程将介绍如何训练神经网络来自主控制真实的机器人。

**你将学到：**

1. 如何记录和可视化您的数据集。
2. 如何使用您的数据训练策略并准备进行评估。
3. 如何评估您的策略并可视化结果。

通过以下步骤，您将能够重现各种任务，例如拾取乐高积木并高成功率地将其放入箱中，如下面的视频所示。

**视频：拾取乐高积木任务**

[](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/lerobot_task.mp4)

本教程不绑定特定的机器人：我们将带您了解可以适配于任何受支持平台的命令和 API 代码片段。

在数据采集期间，您将使用一个“遥操作”设备（例如主臂或键盘）来遥操作机器人并记录其运动轨迹。

收集到足够的轨迹后，您将训练一个神经网络来模仿这些轨迹，并部署训练好的模型，以便您的机器人能够自主执行该任务。

如果您在任何时候遇到任何问题，请加入我们的 [Discord 社区](https://discord.com/invite/s3KuuzsPFb)以获取支持。

## 设置与校准

如果您尚未设置和校准您的机器人及遥操作设备，请按照特定机器人的教程进行操作。

## 遥操作

在此示例中，我们将演示如何遥操作 SO101 机器人。对于每个命令，我们还提供了一个相应的 API 示例。

请注意，与机器人关联的 `id` 用于存储校准文件。在相同的设置下，进行遥操作、记录和评估时，务必使用相同的 `id`。

命令

API 示例

```
lerobot-teleoperate \
    --robot.type=so101_follower \
    --robot.port=/dev/tty.usbmodem58760431541 \
    --robot.id=my_awesome_follower_arm \
    --teleop.type=so101_leader \
    --teleop.port=/dev/tty.usbmodem58760431551 \
    --teleop.id=my_awesome_leader_arm
```

遥操作命令将自动：

1. 识别任何缺失的校准并启动校准程序。
2. 连接机器人和遥操作设备并开始遥操作。

## 相机

要在您的设置中添加相机，请遵循此[指南](cameras.md#setup-cameras)。

## 带相机遥操作

通过 `rerun`，您可以再次进行遥操作，同时可视化相机画面和关节位置。在此示例中，我们使用的是 Koch 机械臂。

命令

API 示例

```
lerobot-teleoperate \
    --robot.type=koch_follower \
    --robot.port=/dev/tty.usbmodem58760431541 \
    --robot.id=my_awesome_follower_arm \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}}" \
    --teleop.type=koch_leader \
    --teleop.port=/dev/tty.usbmodem58760431551 \
    --teleop.id=my_awesome_leader_arm \
    --display_data=true
```

## 录制数据集

一旦您熟悉了远程操作，您就可以记录您的第一个数据集。

我们使用 Hugging Face Hub 的功能来上传您的数据集。如果您以前没有使用过 Hub，请确保可以通过 CLI 使用具有写权限的 Token 进行登录。该 Token 可以在 [Hugging Face 设置](https://hugging-face.cn/settings/tokens)中生成。

通过运行此命令将您的令牌添加到 CLI

```
hf auth login --token ${HUGGINGFACE_TOKEN} --add-to-git-credential
```

然后将您的 Hugging Face 存储库名称存储在一个变量中

```
HF_USER=$(NO_COLOR=1 hf auth whoami | awk -F': *' 'NR==1 {print $2}')
echo $HF_USER
```

现在您可以记录数据集了。要记录 5 个回合（episodes）并将数据集上传到 Hub，请针对您的机器人调整以下代码，并执行命令或 API 示例。

命令

API 示例

```
lerobot-record \
    --robot.type=so101_follower \
    --robot.port=/dev/tty.usbmodem585A0076841 \
    --robot.id=my_awesome_follower_arm \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}}" \
    --teleop.type=so101_leader \
    --teleop.port=/dev/tty.usbmodem58760431551 \
    --teleop.id=my_awesome_leader_arm \
    --display_data=true \
    --dataset.repo_id=${HF_USER}/record-test \
    --dataset.num_episodes=5 \
    --dataset.single_task="Grab the black cube" \
    --dataset.streaming_encoding=true \
    # --dataset.vcodec=auto \
    --dataset.encoder_threads=2
```

#### 数据集上传

在本地，您的数据集存储在此文件夹中：`~/.cache/huggingface/lerobot/{repo-id}`。数据记录结束时，您的数据集将被上传到您的 Hugging Face 页面（例如 `https://hugging-face.cn/datasets/${HF_USER}/so101_test`），您可以通过运行以下命令来获取：

```
echo https://hugging-face.cn/datasets/${HF_USER}/so101_test
```

您的数据集将自动标记为 `LeRobot`，以便社区轻松找到它，您还可以添加自定义标签（例如，在此示例中为 `tutorial`）。

您可以通过搜索 `LeRobot` [标签](https://hugging-face.cn/datasets?other=LeRobot)在 Hub 上查找其他 LeRobot 数据集。

您也可以手动运行以下命令将本地数据集推送到 Hub：

```
hf upload ${HF_USER}/record-test ~/.cache/huggingface/lerobot/{repo-id} --repo-type dataset
```

#### 记录功能

`record` 函数提供了一套在机器人运行期间捕获和管理数据的工具

##### 1. 数据存储

* 数据使用 `LeRobotDataset` 格式存储，并在记录期间保存在磁盘上。
* 默认情况下，记录完成后数据集将被推送到您的 Hugging Face 页面。
  + 若要禁用上传，请使用 `--dataset.push_to_hub=False`。

##### 2. 检查点与恢复

* 记录过程中会自动创建检查点。
* 如果出现问题，您可以通过使用 `--resume=true` 重新运行相同的命令来恢复。恢复记录时，`--dataset.num_episodes` 必须设置为 **要额外记录的回合数**，而不是数据集的目标总回合数！
* 要从头开始记录，请 **手动删除** 数据集目录。

##### 3. 记录参数

使用命令行参数设置数据记录流程

* `--dataset.episode_time_s=60` 每个数据记录回合的持续时间（默认：**60 秒**）。
* `--dataset.reset_time_s=60` 每个回合后重置环境的持续时间（默认：**60 秒**）。
* `--dataset.num_episodes=50` 要记录的总回合数（默认：**50**）。

##### 4. 记录期间的键盘控制

使用键盘快捷键控制数据记录流程

* 按 **右箭头 (`→`)**：提前停止当前回合或重置时间，并进入下一个回合。
* 按 **左箭头 (`←`)**：取消当前回合并重新录制。
* 按 **退出键 (`ESC`)**：立即停止会话、编码视频并上传数据集。

#### 数据采集技巧

一旦您熟悉了数据记录，就可以创建用于训练的更大规模的数据集。一个很好的入门任务是在不同位置抓取物体并将其放入箱中。我们建议至少记录 50 个回合，每个位置记录 10 个回合。在整个记录过程中，保持相机固定并保持一致的抓取动作。还要确保您操作的物体在相机画面中是可见的。一个好的经验法则是：您应该能够仅通过观看相机图像来自己完成该任务。

在接下来的章节中，您将训练您的神经网络。在实现可靠的抓取性能后，您可以开始在数据采集期间引入更多变化，例如增加抓取位置、使用不同的抓取技术以及改变相机位置。

避免过快地添加太多变化，因为它可能会阻碍您的结果。

如果您想深入了解这个重要主题，您可以查看我们撰写的关于什么是一个好的数据集的[博客文章](https://hugging-face.cn/blog/lerobot-datasets#what-makes-a-good-dataset)。

#### 故障排除：

* 在 Linux 上，如果左右方向键和退出键在数据记录期间没有任何效果，请确保您已设置 `$DISPLAY` 环境变量。请参见 [pynput 局限性](https://pynput.readthedocs.io/en/latest/limitations.html#linux)。

## 可视化数据集

如果您已使用 `--control.push_to_hub=true` 将数据集上传到 hub，则可以通过复制并粘贴由以下命令提供的 repo id 来[在线可视化您的数据集](https://hugging-face.cn/spaces/lerobot/visualize_dataset)：

```
echo ${HF_USER}/so101_test
```

## 重放回合

一个非常有用的功能是 `replay`（重放）函数，它允许您重放已记录的任何回合或来自任何现有数据集的回合。此功能可帮助您测试机器人动作的可重复性，并评估相同型号机器人之间的可迁移性。

您可以通过运行以下命令或使用 API 示例在您的机器人上重放第一个回合：

命令

API 示例

```
lerobot-replay \
    --robot.type=so101_follower \
    --robot.port=/dev/tty.usbmodem58760431541 \
    --robot.id=my_awesome_follower_arm \
    --dataset.repo_id=${HF_USER}/record-test \
    --dataset.episode=0 # choose the episode you want to replay
```

您的机器人应该能够重现与您录制的类似的运动。例如，可以观看[这个视频](https://x.com/RemiCadene/status/1793654950905680090)，我们在视频中对来自 [Trossen Robotics](https://www.trossenrobotics.com) 的 Aloha 机器人使用了 `replay`。

## 训练策略

要训练控制机器人的策略，请使用 [`lerobot-train`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/scripts/lerobot_train.py) 脚本。需要提供几个参数。下面是一个示例命令：

```
lerobot-train \
  --dataset.repo_id=${HF_USER}/so101_test \
  --policy.type=act \
  --output_dir=outputs/train/act_so101_test \
  --job_name=act_so101_test \
  --policy.device=cuda \
  --wandb.enable=true \
  --policy.repo_id=${HF_USER}/my_policy
```

让我们来解释一下这个命令：

1. 我们通过 `--dataset.repo_id=${HF_USER}/so101_test` 将数据集作为参数提供。
2. 我们通过 `policy.type=act` 提供了策略。这将从 [`configuration_act.py`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/act/configuration_act.py) 加载配置。重要的是，该策略将自动适应您数据集中保存的机器人电机状态数量、电机动作以及相机数量（例如 `laptop` 和 `phone`）。
3. 我们提供了 `policy.device=cuda`，因为我们是在 Nvidia GPU 上训练，但你也可以使用 `policy.device=mps` 在 Apple 芯片上进行训练。
4. 我们提供了 `wandb.enable=true` 以使用 [Weights and Biases](https://docs.wandb.ai/quickstart) 可视化训练图表。这是可选的，但如果您使用它，请确保通过运行 `wandb login` 进行了登录。

训练应该需要几个小时。您可以在 `outputs/train/act_so101_test/checkpoints` 中找到检查点。

若要从检查点恢复训练，以下是从 `act_so101_test` 策略的 `last`（最新）检查点恢复的示例命令：

```
lerobot-train \
  --config_path=outputs/train/act_so101_test/checkpoints/last/pretrained_model/train_config.json \
  --resume=true
```

如果您不想在训练后将模型推送到 hub，请使用 `--policy.push_to_hub=false`。

此外，您还可以提供额外的 `tags`、为模型指定 `license` 或通过添加以下内容将模型仓库设置为 `private`：`--policy.private=true --policy.tags=\[ppo,rl\] --policy.license=mit`

#### 使用 Google Colab 训练

如果您的本地计算机没有强大的 GPU，您可以按照 [ACT 训练 notebook](notebooks.md#training-act) 利用 Google Colab 训练模型。

#### 上传策略检查点

训练完成后，使用以下命令上传最新的检查点：

```
hf upload ${HF_USER}/act_so101_test \
  outputs/train/act_so101_test/checkpoints/last/pretrained_model
```

你也可以使用以下命令上传中间检查点：

```
CKPT=010000
hf upload ${HF_USER}/act_so101_test${CKPT} \
  outputs/train/act_so101_test/checkpoints/${CKPT}/pretrained_model
```

## 运行推理并评估您的策略

您可以使用来自 [`lerobot-record`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/scripts/lerobot_record.py) 的 `record` 脚本，并将策略检查点作为输入，来运行推理和评估您的策略。例如，运行此命令或 API 示例来运行推理并记录 10 个评估回合：

命令

API 示例

```
lerobot-record  \
  --robot.type=so100_follower \
  --robot.port=/dev/ttyACM1 \
  --robot.cameras="{ up: {type: opencv, index_or_path: /dev/video10, width: 640, height: 480, fps: 30}, side: {type: intelrealsense, serial_number_or_name: 233522074606, width: 640, height: 480, fps: 30}}" \
  --robot.id=my_awesome_follower_arm \
  --display_data=false \
  --dataset.repo_id=${HF_USER}/eval_so100 \
  --dataset.single_task="Put lego brick into the transparent box" \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2 \
  # --dataset.vcodec=auto \
  # <- Teleop optional if you want to teleoperate in between episodes \
  # --teleop.type=so100_leader \
  # --teleop.port=/dev/ttyACM0 \
  # --teleop.id=my_awesome_leader_arm \
  --policy.path=${HF_USER}/my_policy
```

如您所见，这与先前用于记录训练数据集的命令几乎相同。只有两点改变了：

1. 增加了一个额外的 `--control.policy.path` 参数，它指示您的策略检查点的路径（例如 `outputs/train/eval_act_so101_test/checkpoints/last/pretrained_model`）。如果您已将模型检查点上传到 hub，也可以使用模型仓库（例如 `${HF_USER}/act_so101_test`）。
2. 数据集的名称以 `eval` 开头，以反映您正在运行推理（例如 `${HF_USER}/eval_act_so101_test`）。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/il_robots.mdx)
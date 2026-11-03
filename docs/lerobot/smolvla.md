# 来源

https://hugging-face.cn/docs/lerobot/smolvla

# SmolVLA

SmolVLA 是 Hugging Face 为机器人领域打造的轻量级基础模型。它专为在 LeRobot 数据集上进行便捷的微调而设计，旨在加速您的开发进程！

![SmolVLA architecture.](https://cdn-uploads.huggingface.co/production/uploads/640e21ef3c82bd463ee5a76d/aooU0a3DMtYmy_1IWMaIM.png)   
 *图 1. SmolVLA 的输入包括 (i) 多个摄像头视角，(ii) 机器人的当前传感器运动状态，以及 (iii) 自然语言指令。这些输入被编码为上下文特征，用于在生成动作块（action chunk）时对动作专家模型进行条件约束。*

## 配置您的环境

1. 请遵循我们的[安装指南](installation.md)来安装 LeRobot。
2. 通过运行以下命令安装 SmolVLA 的依赖项：

   ```
   pip install -e ".[smolvla]"
   ```

## 收集数据集

SmolVLA 是一个基础模型，因此为了在您的设置中获得最佳性能，需要在您自己的数据上进行微调。我们建议首先录制约 50 个任务片段（episodes）作为起点。请参考我们的指南开始操作：[录制数据集](il_robots.md)

> 在您的数据集中，请确保为您引入的每种变体（例如，如果是立方体拾取放置任务，则为桌上的立方体位置）提供足够的演示数据。
>
> 我们建议参考下方链接的数据集，该数据集曾用于 [SmolVLA 论文](https://hugging-face.cn/papers/2506.01844) 中
>
> 🔗 [SVLA SO100 拾取放置 (PickPlace)](https://hugging-face.cn/spaces/lerobot/visualize_dataset?path=%2Flerobot%2Fsvla_so100_pickplace%2Fepisode_0)
>
> 在该数据集中，我们在 5 个不同的立方体位置上录制了 50 个片段。对于每个位置，我们收集了 10 个拾取和放置交互的片段。这种通过多次重复每个变体来构建的结构有助于模型更好地泛化。我们曾尝试使用包含 25 个片段的类似数据集，但数量不足导致性能不佳。因此，数据的质量和数量绝对是关键。当您的数据集上传至 Hub 后，您就可以使用我们的微调脚本将 SmolVLA 适配到您的应用中。

## 在您的数据上微调 SmolVLA

使用我们预训练的 450M 模型 [`smolvla_base`](https://hugging-face.cn/lerobot/smolvla_base) 并在您的数据上进行微调。在单张 A100 GPU 上，将模型训练 20k 步大约需要 4 小时。您应根据性能和具体用例来调整步数。

如果您没有 GPU 设备，可以使用我们在 [![Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/huggingface/notebooks/blob/main/lerobot/training-smolvla.ipynb) 上的 notebook 进行训练

使用 `--dataset.repo_id` 将您的数据集传递给训练脚本。如果您想测试安装是否正确，可以运行以下命令，这里我们使用了为 [SmolVLA 论文](https://hugging-face.cn/papers/2506.01844) 收集的数据集之一。

```
cd lerobot && lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=${HF_USER}/mydataset \
  --batch_size=64 \
  --steps=20000 \
  --output_dir=outputs/train/my_smolvla \
  --job_name=my_smolvla_training \
  --policy.device=cuda \
  --wandb.enable=true
```

> 您可以从较小的 batch size 开始，如果 GPU 显存允许且加载时间保持在较短范围内，可以逐步增加它。

微调是一门艺术。要全面了解微调的选项，请运行：

```
lerobot-train --help
```

![Comparison of SmolVLA across task variations.](https://cdn-uploads.huggingface.co/production/uploads/640e21ef3c82bd463ee5a76d/S-3vvVCulChREwHDkquoc.gif)   
 *图 2：SmolVLA 在不同任务变体下的对比。从左到右依次为：(1) 立方体拾取放置计数，(2) 立方体拾取放置计数，(3) 扰动下的立方体拾取放置计数，以及 (4) 使用真实 SO101 机器人对乐高积木进行拾取放置的泛化能力。*

## 评估微调后的模型并实时运行

与录制片段时类似，建议您登录 HuggingFace Hub。您可以参考相应步骤：[录制数据集](il_robots.md)。登录后，您可以通过以下操作在您的设置中运行推理：

```
lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \ # <- Use your port
  --robot.id=my_blue_follower_arm \ # <- Use your robot id
  --robot.cameras="{ front: {type: opencv, index_or_path: 8, width: 640, height: 480, fps: 30}}" \ # <- Use your cameras
  --dataset.single_task="Grasp a lego block and put it in the bin." \ # <- Use the same task description you used in your dataset recording
  --dataset.repo_id=${HF_USER}/eval_DATASET_NAME_test \  # <- This will be the dataset name on HF Hub
  --dataset.episode_time_s=50 \
  --dataset.num_episodes=10 \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2 \
  # --dataset.vcodec=auto \
  # <- Teleop optional if you want to teleoperate in between episodes \
  # --teleop.type=so100_leader \
  # --teleop.port=/dev/ttyACM0 \
  # --teleop.id=my_red_leader_arm \
  --policy.path=HF_USER/FINETUNE_MODEL_NAME # <- Use your fine-tuned model
```

根据您的评估设置，您可以为评估套件配置录制的时长和片段数量。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/smolvla.mdx)
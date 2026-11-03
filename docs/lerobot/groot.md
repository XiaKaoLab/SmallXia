# 来源

https://hugging-face.cn/docs/lerobot/groot

# GR00T N1.5 策略

GR00T N1.5 是 NVIDIA 推出的开源基础模型，旨在为通用人形机器人提供推理能力和技能。它是一个跨具身模型，能够接收包括语言和图像在内的多模态输入，以在多样化的环境中执行操纵任务。

本文档概述了该模型在 LeRobot 框架中的集成和使用细节。

## 模型概述

NVIDIA Isaac GR00T N1.5 是 GR00T N1 基础模型的升级版本。其构建目标是提高人形机器人的泛化能力和指令遵循能力。

开发者和研究人员可以使用自己的真实数据或合成数据对 GR00T N1.5 进行后训练（post-train），以使其适配特定的人形机器人或任务。

GR00T N1.5（具体为 GR00T-N1.5-3B 模型）基于预训练的视觉和语言编码器构建。它利用流匹配动作变换器（flow matching action transformer）在视觉、语言和本体感受的条件下对一组动作块进行建模。

![An overview of GR00T](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/lerobot-groot-paper1%20(1).png)

其强大的性能得益于在规模宏大且多样的人形机器人数据集上进行训练，该数据集包括：

* 来自机器人的真实采集数据。
* 使用 NVIDIA Isaac GR00T Blueprint 生成的合成数据。
* 互联网规模的视频数据。

这种方法使得模型能够通过针对特定具身、任务和环境的后训练而具有高度的适应性。

## 安装要求

截至目前，GR00T N1.5 的内部运行需要 flash attention 支持。

我们正在努力将其设为可选，但在目前阶段，这意味着需要额外的安装步骤，且仅能在支持 CUDA 的设备上使用。

1. 请参考我们的 [安装指南](installation.md) 中的环境设置。**注意：**在此步骤中请勿安装 `lerobot`。
2. 运行以下命令安装 [Flash Attention](https://github.com/Dao-AILab/flash-attention)：

```
# Check https://pytorch.ac.cn/get-started/locally/ for your system
pip install "torch>=2.2.1,<2.8.0" "torchvision>=0.21.0,<0.23.0" # --index-url https://download.pytorch.org/whl/cu1XX
pip install ninja "packaging>=24.2,<26.0" # flash attention dependencies
pip install "flash-attn>=2.5.9,<3.0.0" --no-build-isolation
python -c "import flash_attn; print(f'Flash Attention {flash_attn.__version__} imported successfully')"
```

3. 运行以下命令安装 LeRobot：

```
pip install lerobot[groot]
```

## 用法

要在 LeRobot 配置中使用 GR00T，请将策略类型（policy type）指定为：

```
policy.type=groot
```

## 训练

### 训练命令示例

以下是在您自己的数据集上微调 GR00T 基础模型的完整训练命令：

```
# Using a multi-GPU setup
accelerate launch \
  --multi_gpu \
  --num_processes=$NUM_GPUS \
  $(which lerobot-train) \
  --output_dir=$OUTPUT_DIR \
  --save_checkpoint=true \
  --batch_size=$BATCH_SIZE \
  --steps=$NUM_STEPS \
  --save_freq=$SAVE_FREQ \
  --log_freq=$LOG_FREQ \
  --policy.push_to_hub=true \
  --policy.type=groot \
  --policy.repo_id=$REPO_ID \
  --policy.tune_diffusion_model=false \
  --dataset.repo_id=$DATASET_ID \
  --wandb.enable=true \
  --wandb.disable_artifact=true \
  --job_name=$JOB_NAME
```

## 性能结果

### Libero 基准测试结果

> 请参考 Libero 使用说明：[Libero](libero.md)

GR00T 在 Libero 基准测试套件中表现出了强劲的性能。为了对比并测试其 LeRobot 实现，我们在 Libero 数据集上对 GR00T N1.5 模型进行了 30k 步的微调，并将结果与 GR00T 的参考结果进行了对比。

| 基准测试 | LeRobot 实现 | GR00T 参考 |
| --- | --- | --- |
| **Libero Spatial** | 82.0% | 92.0% |
| **Libero Object** | 99.0% | 92.0% |
| **Libero Long** | 82.0% | 76.0% |
| **平均分** | 87.0% | 87.0% |

这些结果证明了 GR00T 在多样化的机器人操纵任务中具有强大的泛化能力。要复现这些结果，您可以参考 [Libero](libero.md) 章节中的说明。

### 在您的硬件设置中进行评估

使用您的参数训练好模型后，您可以在下游任务中运行推理。请参考 [机器人模仿学习](il_robots.md) 中的说明。例如：

```
lerobot-record \
  --robot.type=bi_so_follower \
  --robot.left_arm_port=/dev/ttyACM1 \
  --robot.right_arm_port=/dev/ttyACM0 \
  --robot.id=bimanual_follower \
  --robot.cameras='{ right: {"type": "opencv", "index_or_path": 0, "width": 640, "height": 480, "fps": 30},
    left: {"type": "opencv", "index_or_path": 2, "width": 640, "height": 480, "fps": 30},
    top: {"type": "opencv", "index_or_path": 4, "width": 640, "height": 480, "fps": 30},
  }' \
  --display_data=true \
  --dataset.repo_id=<user>/eval_groot-bimanual  \
  --dataset.num_episodes=10 \
  --dataset.single_task="Grab and handover the red cube to the other arm" \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2 \
  # --dataset.vcodec=auto \
  --policy.path=<user>/groot-bimanual \ # your trained model
  --dataset.episode_time_s=30 \
  --dataset.reset_time_s=10
```

## 许可证

本模型遵循 NVIDIA 的专有许可，与原始 [GR00T 仓库](https://github.com/NVIDIA/Isaac-GR00T) 一致。未来版本（从 N1.7 开始）将遵循 **Apache 2.0 许可证**。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/groot.mdx)
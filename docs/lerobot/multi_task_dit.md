# 来源

https://hugging-face.cn/docs/lerobot/multi_task_dit

# Multitask DiT 策略

多任务扩散 Transformer (DiT) 策略是原始扩散策略 (Diffusion Policy) 架构的进化版，它利用带有文本和视觉条件的超大 DiT 进行多任务机器人学习。该实现支持动作生成的扩散 (diffusion) 和流匹配 (flow matching) 目标，使机器人能够根据语言指令执行多样的操作任务。

## 模型概述

该模型使用：

* **CLIP 视觉编码器**：处理来自多个摄像机视角的 RGB 图像
* **CLIP 文本编码器**：对语言任务指令进行编码（具有可学习投影的冻结权重）
* **扩散 Transformer**：根据观察结果和语言预测动作序列
* **两个目标**：支持动作生成的扩散 (DDPM/DDIM) 和流匹配

这个模型非常令人兴奋，因为只需约 4.5 亿个参数和明显更少的训练，你就可以实现极高的灵活性，足以与拥有数十亿参数的 VLA 模型竞争。

## 安装要求

Multitask DiT 策略有额外的依赖项。请使用以下命令安装：

```
pip install lerobot[multi_task_dit]
```

这将安装所有必要的依赖项，包括用于 CLIP 模型的 HuggingFace Transformers 库。

## 用法

要在您的 LeRobot 配置中使用 Multitask DiT，请将策略类型指定为：

```
policy.type=multi_task_dit
```

## 训练

### 基础训练命令

以下是在您的数据集上训练 Multitask DiT 的完整训练命令：

```
lerobot-train \
  --dataset.repo_id=YOUR_DATASET \
  --output_dir=./outputs/multitask_dit_training \
  --batch_size=32 \
  --steps=5000 \
  --save_freq=500 \
  --log_freq=100 \
  --policy.type=multi_task_dit \
  --policy.device=cuda \
  --policy.repo_id="HF_USER/multitask-dit-your-robot" \
  --wandb.enable=true
```

### 推荐超参数和数据集详情 (30Hz 控制频率)

为了获得可靠的性能，请从这些建议的默认超参数开始：

```
lerobot-train \
  --dataset.repo_id=YOUR_DATASET \
  --output_dir=./outputs/mutitask_dit_training \
  --batch_size=320 \
  --steps=30000 \
  --policy.type=multi_task_dit \
  --policy.device=cuda \
  --policy.horizon=32 \
  --policy.n_action_steps=24 \
  --policy.objective=diffusion \
  --policy.noise_scheduler_type=DDPM \
  --policy.num_train_timesteps=100 \
  --policy.repo_id="HF_USER/multitask-dit-your-robot" \
  --wandb.enable=true
```

**关键参数**

* **Batch Size**: 192-320 - 如果您的 GPU 支持该大小，您将获得最佳的训练动态
* **Horizon**: 32 - 要预测的动作步数，30Hz 时约 1.0 秒
* **n\_action\_steps**: 24 - 30Hz 时约 0.8 秒
* **Objective (目标)**: `diffusion` - 从扩散开始，如果生成质量差，再尝试流匹配
* **训练步数**：单任务建议训练步数 >30k

### 训练配置参数

#### 目标选择

在扩散和流匹配之间进行选择

```
# Diffusion objective (default)
--policy.objective=diffusion \
--policy.noise_scheduler_type=DDPM \  # or "DDIM"
--policy.num_train_timesteps=100 \
--policy.num_inference_steps=10 \  # For faster inference
--policy.beta_schedule=squaredcos_cap_v2 \  # Noise schedule type
--policy.prediction_type=epsilon \  # "epsilon" (predict noise) or "sample" (predict clean)
--policy.clip_sample=true \  # Clip samples during denoising
--policy.clip_sample_range=1.0  # Clipping range [-x, x]

# Flow matching objective
--policy.objective=flow_matching \
--policy.timestep_sampling_strategy=beta \  # or "uniform" | the beta sampling strategy performance appears much better in practice
--policy.num_integration_steps=100 \
--policy.integration_method=euler \  # or "rk4"
--policy.sigma_min=0.0  # Minimum noise in flow interpolation path
```

#### Transformer 架构

根据数据集大小调整模型容量

```
# Small datasets (< 100 examples)
--policy.num_layers=4 \
--policy.hidden_dim=512 \
--policy.num_heads=8  # should ideally be hidden_dim // 64

# Medium datasets (100-5k examples) - default
--policy.num_layers=6 \
--policy.hidden_dim=512 \
--policy.num_heads=8  # should ideally be hidden_dim // 64

# Large datasets (> 5k examples)
--policy.num_layers=8 \
--policy.hidden_dim=512 \
--policy.num_heads=8   # should ideally be hidden_dim // 64
```

**位置编码选项**

模型为动作序列支持两种位置编码方法

```
# Rotary Position Embedding (RoPE) - default, recommended
--policy.use_rope=true \
--policy.rope_base=10000.0  # Base frequency for RoPE

# Absolute positional encoding
--policy.use_positional_encoding=true  # Disables RoPE when true
```

**其他 Transformer 参数**

```
--policy.dropout=0.1  # Dropout rate for DiT blocks (0.0-1.0)
--policy.timestep_embed_dim=256  # Timestep embedding dimension
```

#### 视觉编码器配置

```
# Use different CLIP model for more expressivity at the cost of inference time
# experiment with larger or smaller models depending on the complexity of your tasks and size of dataset
--policy.vision_encoder_name=openai/clip-vit-large-patch14

# Use separate vision encoder per camera
# This may be useful when cameras have significantly different characteristics, but
# be wary of increased VRAM footprint.
--policy.use_separate_rgb_encoder_per_camera=true

# Image preprocessing
--policy.image_resize_shape=[XXX,YYY] \ # you may need to resize your images for inference speed ups
--policy.image_crop_shape=[224,224] \
--policy.image_crop_is_random=true  # Random during training, center at inference
```

#### 文本编码器配置

```
# Use different CLIP text encoder model
# same as vision: experiment with larger or smaller models depending on the
# complexity of your tasks and size of dataset
--policy.text_encoder_name=openai/clip-vit-large-patch14
```

#### 学习率配置

视觉编码器使用单独的学习率乘数，建议将 1/10 作为理想的起始点

```
--policy.optimizer_lr=2e-5 \
--policy.vision_encoder_lr_multiplier=0.1  # Vision encoder LR = 0.1 * optimizer_lr
```

### 训练微调指南

#### 1. 使用 Beta 采样的流匹配

此处的原始扩散实现是基于 [TRI 的 LBM 论文](https://arxiv.org/abs/2507.05331) 中描述的工作

此外，我们实现了一个流匹配目标，在 [Boston Dynamics 博客文章](https://bostondynamics.com/blog/large-behavior-models-atlas-find-new-footing/) 中对其进行了高层描述。

考虑测试流匹配目标并评估您任务中的性能差异

```
--policy.objective=flow_matching \
--policy.timestep_sampling_strategy=beta \
--policy.timestep_sampling_alpha=1.5 \
--policy.timestep_sampling_beta=1.0 \
--policy.timestep_sampling_s=0.999
```

这虽不能证明是适用于每种情况的灵丹妙药，但偶尔能产生更平滑、更一致的动作。

#### 2. Transformer 层数

使模型容量与您的数据集大小相匹配

* **小型数据集**（< 100 个样本）：减少到 4 层
* **大型数据集**（> 5k 个样本）：增加到 8 层

#### 3. horizon (预测时界) 微调

模型可能对您选择的 horizon 很敏感。根据您的控制频率，从大约 1 秒的 horizon 开始

* **30 Hz 频率**: `horizon=30`
* **10 Hz 频率**: `horizon=10`

然后尝试在此基础上增加。horizon 决定了模型预测未来动作的深度。

#### 4. n\_action\_steps (执行步数) 敏感度

模型也可能对 `n_action_steps` 非常敏感。根据您的控制频率，从大约 0.8 秒开始，然后进行微调

* **较低值**：反应更敏捷，但在长时界任务中可能不太稳定
* **较高值**：更利于长时界执行，但开环失败时的恢复能力有限

### 推理微调

为了实现更快的推理，请使用采样步数更少的 DDIM

```
--policy.noise_scheduler_type=DDIM \
--policy.num_inference_steps=10
```

### 恢复训练

从检查点恢复训练：

```
lerobot-train \
  --config_path=./outputs/mutitask_dit_training/checkpoints/last/pretrained_model/train_config.json \
  --resume=true
```

检查点目录应包含 `model.safetensors` 和 `config.json` 文件（在训练期间自动保存）。恢复时，配置将从检查点加载，因此无需指定其他参数。

## 常见故障模式与调试

训练这些模型可能比较棘手。以下是一些常见的故障模式及调试方法：

### 怠速 / 无动作

模型可能会在推理期间“崩溃”，导致动作静止或无动作。这种情况可能发生在：

1. **训练数据不足**：如果您只有 20-50 个样本，请尝试将数据集大小增加约一倍。如果样本量超过 300 个仍出现此情况，可能是任务过于复杂。
2. **多个类似任务**：当您的数据集中包含多个类似任务（例如，拾取 2 个不同的物体）时，模型可能过于依赖语言调节，而语言条件可能不够丰富。

**调试提示：**

* 增加数据集大小（翻倍，直到样本量超过 300 个）
* 训练更长时间（高达 100k 步），即使损失函数已趋于平缓
* 检查模型是否收到了正确的语言指令，或增加指令的多样性

### 执行了错误的任务

有时机器人会完全忽略您的指令而执行其他任务。这通常只在您进行了多任务训练的情况下发生。

**潜在原因：**

* 语言指令不明确
* 任务特定的训练数据不足
* 模型对多任务数据集中类似任务的混淆

**调试提示：**

* 核实语言指令的特异性，尤其是当多个任务之间的描述相似时
* 检查训练数据集中的任务分布，并为失败/被忽略的任务增加权重
* 考虑进行任务特定的微调

### 训练不稳定

如果训练损失不稳定或发散：

* 尝试在 `1e-5` 和 `3e-4` 之间调整学习率
* 尽可能增加 Batch Size
* 检查您的数据集归一化是否正确
* 确认图像预处理工作是否正常

## 性能考量

### GPU 要求

* **推理**：建议至少使用 RTX 5070 Ti（或同等 GPU）以获得合理的执行速度
* **训练**：拥有足够显存以加载 >64 batch size 的 GPU 是理想的，具体取决于图像观察值的数量等因素

### Batch Size 建议

* **最小值**：64（低于此值可能导致训练不稳定）
* **推荐值**：256-320（性能最佳，但需要更大的 GPU）

## 示例：在自定义数据集上进行训练

以下是在自定义数据集上训练的完整示例：

```
lerobot-train \
  --dataset.repo_id=YOUR_DATASET \
  --output_dir=./outputs/mutitask_dit_training \
  --batch_size=320 \
  --steps=30000 \
  --save_freq=1000 \
  --log_freq=100 \
  --eval_freq=1000 \
  --policy.type=multi_task_dit \
  --policy.device=cuda \
  --policy.horizon=32 \
  --policy.n_action_steps=24 \
  --policy.objective=diffusion \
  --policy.noise_scheduler_type=DDPM \
  --policy.num_layers=6 \
  --policy.hidden_dim=512 \
  --policy.vision_encoder_name=openai/clip-vit-base-patch16 \
  --policy.image_resize_shape=[320,240] \
  --policy.image_crop_shape=[224,224] \
  --policy.repo_id="HF_USER/multitask-dit-your-robot" \
  --wandb.enable=true \
  --wandb.project=multitask_dit
```

## Libero 结果

```
python -m lerobot.scripts.lerobot_train \
  --dataset.repo_id=HuggingFaceVLA/libero \
  --policy.type=multi_task_dit \
  --policy.push_to_hub=false \
  --output_dir="./outputs/multitask_dit_libero" \
  --job_name="multitask-dit-libero" \
  --wandb.enable=true \
  --wandb.project=multitask_dit_libero \
  --dataset.image_transforms.enable=true \
  --dataset.image_transforms.max_num_transforms=4 \
  --dataset.image_transforms.tfs='{"brightness":{"type":"ColorJitter","kwargs":{"brightness":[0.75,1.25]}},"contrast":{"type":"ColorJitter","kwargs":{"contrast":[0.6,1.4]}},"saturation":{"type":"ColorJitter","kwargs":{"saturation":[0.8,1.2]}},"hue":{"type":"ColorJitter","kwargs":{"hue":[-0.05,0.05]}},"sharpness":{"type":"SharpnessJitter","kwargs":{"sharpness":[0.6,1.4]}},"rotation":{"type":"RandomRotation","kwargs":{"degrees":[-5,5]}},"translation":{"type":"RandomAffine","kwargs":{"degrees":0,"translate":[0.1,0.1]}}}' \
  --dataset.video_backend=torchcodec \
  --policy.use_amp=true \
  --policy.horizon=48 \
  --policy.n_obs_steps=2 \
  --policy.use_rope=true \
  --policy.use_positional_encoding=false \
  --policy.hidden_dim=768 \
  --policy.num_layers=8 \
  --policy.num_heads=12 \
  --policy.dropout=0.1 \
  --policy.timestep_embed_dim=256 \
  --policy.objective=diffusion \
  --policy.optimizer_lr=3e-4 \
  --policy.optimizer_weight_decay=0 \
  --policy.scheduler_warmup_steps=0 \
  --policy.vision_encoder_name=openai/clip-vit-base-patch16 \
  --policy.image_resize_shape=[256,256] \
  --policy.image_crop_is_random=true \
  --policy.text_encoder_name=openai/clip-vit-base-patch16 \
  --policy.vision_encoder_lr_multiplier=0.1 \
  --policy.device=cuda \
  --num_workers=8 \
  --save_freq=4000 \
  --log_freq=100 \
  --steps=100000 \
  --batch_size=320
```

结果

| LIBERO Spatial | LIBERO Object | LIBERO Goal | LIBERO 10 | 平均分 |
| --- | --- | --- | --- | --- |
| 87.0 | 98.2 | 93.8 | 83.2 | 90.6 |

## 参考文献

有关技术实现和架构的更多详情，请参阅：

* [《对多任务灵巧操作的大型行为模型之仔细检查》 (A Careful Examination of Large Behavior Models for Multitask Dexterous Manipulation)](https://arxiv.org/abs/2507.05331)
* [《大型行为模型和 Atlas 的新突破》 (Large Behavior Models and Atlas Find New Footing)](https://bostondynamics.com/blog/large-behavior-models-atlas-find-new-footing/)
* [《解构并开源 Multitask DiT 策略》 (Dissecting and Open-Sourcing Multitask Diffusion Transformer Policy)](https://brysonkjones.substack.com/p/dissecting-and-open-sourcing-multitask-diffusion-transformer-policy)

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/multi_task_dit.mdx)
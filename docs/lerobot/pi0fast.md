# 来源

https://hugging-face.cn/docs/lerobot/pi0fast

# π₀-FAST (Pi0-FAST)

π₀-FAST 是一款用于**通用机器人控制的视觉-语言-动作 (VLA) 模型**，它使用自回归的下一个 Token 预测来建模连续的机器人动作。

## 模型概述

π₀-FAST 将视觉-语言模型 (VLM) 的强大功能与一种名为 **FAST (频域动作序列标记化，Frequency-space Action Sequence Tokenization)** 的新型动作标记化方法相结合。这使得在处理高灵活性任务时，能够训练出自回归 VLA 模型（这是标准基于分箱的离散化方法无法实现的），且训练速度**比基于扩散模型的方法（如 π₀）快达 5 倍**。

![An overview of Pi0-FAST](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/lerobot-pifast.png)

### 为什么选择 FAST？

标准的机器人动作标记化方法使用简单的按维度、按时间步的分箱方案。虽然对于简单行为尚可，但面对需要高精度和高频控制的复杂与高灵活性技能时，这种方法很快就会失效。

FAST 通过使用信号处理技术压缩动作序列解决了这个问题，生成了一串密集的动作 Token，可以像处理语言 Token 一样进行自回归预测。

### FAST 标记化是如何工作的

FAST 分词器通过以下步骤压缩动作序列：

1. **归一化 (Normalize)**：取形状为 `(H, D)` 的连续动作块，其中 `H` 是时间跨度，`D` 是动作维度。使用支持的归一化方法之一进行归一化（推荐使用分位数法以处理异常值）。
2. **离散余弦变换 (DCT)**：对每个动作维度分别应用 DCT（通过 scipy）。DCT 是一种常用于图像和音频编码（如 JPEG、MP3）的压缩算法。
3. **量化 (Quantization)**：对每个动作维度进行取整并移除不显著的系数，生成稀疏频率矩阵。
4. **展平 (Flatten)**：将矩阵展平为一维向量，低频分量在前。
5. **字节对编码 (BPE)**：训练一个 BPE 分词器将 DCT 系数压缩为密集的动作 Token，通常比先前的标记化方法**实现 10 倍的压缩率**。

这种方法可以通过训练**任何现有 VLM** 来预测这些 FAST Token，从而将其转化为 VLA 模型。

## 安装要求

1. 请遵循我们的[安装指南](installation.md)来安装 LeRobot。
2. 通过运行以下命令安装 π₀-FAST 依赖项

   ```
   pip install -e ".[pi]"
   ```

## 训练自定义 FAST 分词器

您有两种选择来使用 FAST 分词器

1. **使用预训练分词器**：`lerobot/fast-action-tokenizer` 是在超过 100 万个真实机器人动作序列上训练的，可作为通用分词器使用。
2. **训练您自己的分词器**：为了在您的特定数据集上获得最佳性能，您可以根据自己的数据微调分词器。

### 训练您自己的分词器

```
lerobot-train-tokenizer \
    --repo_id "user/my-lerobot-dataset" \
    --action_horizon 10 \
    --encoded_dims "0:6" \
    --vocab_size 1024 \
    --scale 10.0 \
    --normalization_mode QUANTILES \
    --output_dir "./my_fast_tokenizer" \
    --push_to_hub \
    --hub_repo_id "username/my-action-tokenizer"
```

### 关键分词器参数

| 参数 | 描述 | 默认 |
| --- | --- | --- |
| `--repo_id` | LeRobot 数据集仓库 ID | 必需 |
| `--action_horizon` | 每个数据块中未来动作的数量 | `10` |
| `--encoded_dims` | 需要编码的逗号分隔的维度范围（例如 `"0:6,7:23"`） | `"0:6,7:23"` |
| `--vocab_size` | BPE 词汇表大小 | `1024` |
| `--scale` | 用于量化的 DCT 缩放因子 | `10.0` |
| `--normalization_mode` | 归一化模式 (`MEAN_STD`, `MIN_MAX`, `QUANTILES`, `QUANTILE10`, `IDENTITY`) | `QUANTILES` |
| `--sample_fraction` | 每个片段采样的数据块比例 | `0.1` |

## 用法

要在 LeRobot 中使用 π₀-FAST，请指定策略类型为

```
policy.type=pi0_fast
```

## 训练

训练 π₀-FAST 时，您可以使用 LeRobot 训练脚本

```
lerobot-train \
    --dataset.repo_id=your_dataset \
    --policy.type=pi0_fast \
    --output_dir=./outputs/pi0fast_training \
    --job_name=pi0fast_training \
    --policy.pretrained_path=lerobot/pi0_fast_base \
    --policy.dtype=bfloat16 \
    --policy.gradient_checkpointing=true \
    --policy.chunk_size=10 \
    --policy.n_action_steps=10 \
    --policy.max_action_tokens=256 \
    --steps=100000 \
    --batch_size=4 \
    --policy.device=cuda
```

### 关键训练参数

| 参数 | 描述 | 默认 |
| --- | --- | --- |
| `--policy.gradient_checkpointing=true` | 在训练期间显著减少内存使用 | `false` |
| `--policy.dtype=bfloat16` | 使用混合精度训练以提高效率 | `float32` |
| `--policy.chunk_size` | 要预测的动作步数（动作跨度） | `50` |
| `--policy.n_action_steps` | 要执行的动作步数 | `50` |
| `--policy.max_action_tokens` | 每个动作块的最大 FAST Token 数 | `256` |
| `--policy.action_tokenizer_name` | 要使用的 FAST 分词器 | `lerobot/fast-action-tokenizer` |
| `--policy.compile_model=true` | 启用 torch.compile 以加快训练速度 | `false` |

## 推理

### 用于快速推理的 KV 缓存

π₀-FAST 支持 **KV 缓存**，这是 LLM 推理中广泛使用的优化手段。它缓存了注意力机制中的键值对，避免了自回归解码过程中的冗余计算。

```
# KV-caching is enabled by default
policy.use_kv_cache=true
```

### 推理示例

```
from lerobot.policies.pi0_fast import PI0FastPolicy, PI0FastConfig

# Load the policy
policy = PI0FastPolicy.from_pretrained("your-model-path")

# During inference
actions = policy.predict_action_chunk(batch)
```

## 模型架构

π₀-FAST 使用基于 PaliGemma 的架构

* **视觉编码器**：用于图像理解的 SigLIP 视觉塔
* **语言模型**：用于处理语言指令并预测动作 Token 的 Gemma 2B 模型

该模型以图像、文本指令和机器人状态为输入，输出离散的 FAST Token，然后将其解码回连续的动作。

## 配置选项

| 参数 | 描述 | 默认 |
| --- | --- | --- |
| `paligemma_variant` | VLM 主干变体 (`gemma_300m`, `gemma_2b`) | `gemma_2b` |
| `max_state_dim` | 最大状态向量维度（填充后） | `32` |
| `max_action_dim` | 最大动作向量维度（填充后） | `32` |
| `temperature` | 采样温度 (0.0 表示贪婪采样) | `0.0` |
| `max_decoding_steps` | 最大解码步数 | `256` |
| `use_kv_cache` | 启用 KV 缓存以加快推理速度 | `true` |

## 与 π₀ 的比较

| 特性 | π₀ | π₀-FAST |
| --- | --- | --- |
| 动作表示 | 流匹配 (扩散模型) | 自回归 Token (FAST) |
| 训练速度 | 1 倍 | **快 5 倍** |
| 灵活性 (Dexterity) | 高 | 高 |
| 推理方法 | 迭代去噪 | 自回归解码 |
| KV 缓存 | 不适用 | 支持 |

## 复现 π₀Fast 结果

我们使用 LeRobot 实现复现了 π₀Fast 在 LIBERO 基准测试上的结果。我们采用了 LeRobot PiFast 基础模型 [lerobot/pi0fast-base](https://hugging-face.cn/lerobot/pi0fast-base)，并使用 [HuggingFace LIBERO 数据集](https://hugging-face.cn/datasets/HuggingFaceVLA/libero)，在 8 张 H100 GPU 上，以 bfloat16 精度、256 的 Batch Size 额外微调了 40k 步。

微调后的模型可以在此处找到

* **π₀Fast LIBERO**: [lerobot/pi0fast-libero](https://hugging-face.cn/lerobot/pi0fast-libero)

使用以下训练命令

```
lerobot-train \
  --dataset.repo_id=lerobot/libero \
  --output_dir=outputs/libero_pi0fast \
  --job_name=libero_pi0fast \
  --policy.path=lerobot/pi0fast_base \
  --policy.dtype=bfloat16 \
  --steps=100000 \
  --save_freq=20000 \
  --batch_size=4 \
  --policy.device=cuda \
  --policy.scheduler_warmup_steps=4000 \
  --policy.scheduler_decay_steps=100000 \
  --policy.scheduler_decay_lr=1e-5 \
  --policy.gradient_checkpointing=true \
  --policy.chunk_size=10 \
  --policy.n_action_steps=10 \
  --policy.max_action_tokens=256 \
  --policy.empty_cameras=1 \
```

然后，我们通过运行以下命令，使用 LeRobot LIBERO 实现来评估微调后的模型

```
tasks="libero_object,libero_spatial,libero_goal,libero_10"
lerobot-eval \
  --policy.path=lerobot/pi0fast-libero \
  --policy.max_action_tokens=256 \
  --env.type=libero \
  --policy.gradient_checkpointing=false \
  --env.task=${tasks} \
  --eval.batch_size=1 \
  --eval.n_episodes=1 \
  --rename_map='{"observation.images.image":"observation.images.base_0_rgb","observation.images.image2":"observation.images.left_wrist_0_rgb"}'
```

**注意：**我们设置 `n_action_steps=10`，与最初的 OpenPI 实现一致。

### 结果

我们在 LIBERO 基准测试上获得了以下结果

| 模型 | LIBERO Spatial | LIBERO Object | LIBERO Goal | LIBERO 10 | 平均分 |
| --- | --- | --- | --- | --- | --- |
| **π₀-fast** | 70.0 | 100.0 | 100.0 | 60.0 | **82.5** |

包含视频在内的完整评估输出文件夹可在此处获取 [here](https://drive.google.com/drive/folders/1HXpwPTRm4hx6g1sF2P7OOqGG0TwPU7LQ?usp=sharing)

## 许可证

此模型遵循 \*\*Apache 2.0 许可证\*\*，与原始的 [OpenPI 仓库](https://github.com/Physical-Intelligence/openpi)一致。

## 参考文献

* [FAST：高效机器人动作标记化](https://www.physicalintelligence.company/research/fast) - Physical Intelligence 博客
* [OpenPI 仓库](https://github.com/Physical-Intelligence/openpi) - 原始实现
* [Hugging Face 上的 FAST 分词器](https://hugging-face.cn/physical-intelligence/fast) - 预训练分词器

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/pi0fast.mdx)
# 来源

https://hugging-face.cn/docs/lerobot/rename_map

# 重命名映射与空摄像头

当你使用机器人策略进行训练、评估或记录时，你的**数据集**或**环境**提供的一组键（例如 `observation.images.front`，`observation.images.eagle`）下的观测值，而你的**策略**则期望另一组键（例如 `observation.images.image`，`observation.images.image2`）。**重命名映射 (rename map)** 可以在不更改策略或数据源的情况下弥补这一差距。

> **范围：**重命名映射仅重命名**观测 (observation)** 键（图像和状态）。动作 (Action) 键不受影响。

## 为什么观测键不总是匹配

策略在其预训练配置中内置了一组固定的**输入特征名称**。例如：

* [pi0fast-libero](https://hugging-face.cn/lerobot/pi0fast-libero) 期望 `observation.images.base\_0\_rgb` 和 `observation.images.left\_wrist\_0\_rgb`。
* [xvla-base](https://hugging-face.cn/lerobot/xvla-base) 期望 `observation.images.image`，`observation.images.image2` 和 `observation.images.image3`。

你的数据集可能使用了完全不同的名称（例如 `observation.images.front`，`observation.images.eagle`，`observation.images.glove`），而你的评估环境可能又使用另一组。与其编辑策略配置或重命名数据集中的列，不如传递一个**重命名映射**：一个将源键映射到策略预期键的 JSON 字典。重命名发生在预处理器流水线内部，因此策略始终能看到其预期的键。

## 使用重命名映射

在命令行中将映射作为 JSON 字符串传递。约定格式始终为：

```
--rename_map='{"source_key": "policy_key", ...}'
```

其中 **source\_key** 是数据集或环境提供的内容，而 **policy\_key** 是策略期望的内容。

只有列出的键会被重命名；所有其他内容都原样传递。条目的顺序并不重要。

支持的策略：**PI0**, **PI05**, **PI0Fast**, **SmolVLA**, 和 **XVLA**。

### 训练

假设你在一个图像键为 `observation.images.front`，`observation.images.eagle` 和 `observation.images.glove` 的数据集上微调 [lerobot/xvla-base](https://hugging-face.cn/lerobot/xvla-base)。XVLA 期望 `observation.images.image`，`observation.images.image2` 和 `observation.images.image3`

```
lerobot-train \
  --dataset.repo_id=YOUR_DATASET \
  --output_dir=./outputs/xvla_training \
  --job_name=xvla_training \
  --policy.path="lerobot/xvla-base" \
  --policy.repo_id="HF_USER/xvla-your-robot" \
  --policy.dtype=bfloat16 \
  --policy.action_mode=auto \
  --steps=20000 \
  --policy.device=cuda \
  --policy.freeze_vision_encoder=false \
  --policy.freeze_language_encoder=false \
  --policy.train_policy_transformer=true \
  --policy.train_soft_prompts=true \
  --rename_map='{"observation.images.front": "observation.images.image", "observation.images.eagle": "observation.images.image2", "observation.images.glove": "observation.images.image3"}'
```

### 评估

一个期望 `observation.images.base\_0\_rgb` 和 `observation.images.left\_wrist\_0\_rgb` 的策略（例如 [pi0fast-libero](https://hugging-face.cn/lerobot/pi0fast-libero)），但 LIBERO 环境返回的是 `observation.images.image` 和 `observation.images.image2`

```
lerobot-eval \
  --policy.path=lerobot/pi0fast-libero \
  --env.type=libero \
  ... \
  --rename_map='{"observation.images.image": "observation.images.base_0_rgb", "observation.images.image2": "observation.images.left_wrist_0_rgb"}'
```

### 记录

`lerobot-record` 也支持重命名映射，嵌套在数据集配置下

```
lerobot-record \ # When running inference
  --policy.path="<user>/smolVLA_finetuned" \
  ... \
  --dataset.rename_map='{"observation.images.glove2": "observation.images.image"}'
```

## 替代方案：直接编辑策略配置

如果你始终使用相同的数据集或环境，你可以**编辑策略的 `config.json`**，使其观测键与你的数据源匹配。这样就不需要重命名映射了。

权衡：修改策略配置会将其与单个数据源绑定。而重命名映射可以让一个策略在多个数据集和环境之间通用。

## 空摄像头：视角少于策略期望的数量

某些策略是为固定数量的图像输入而构建的。如果你的数据集摄像头较少，你可以在策略配置中设置 **`empty_cameras`**，而不是修改模型架构。

### 工作原理

设置 `empty_cameras=N` 会在策略配置中添加 N 个占位图像特征，命名为：

```
observation.images.empty_camera_0
observation.images.empty_camera_1
...
```

在运行时，这些键在批次中没有对应的数据。策略会用掩码伪张量填充它们（对于基于 SigLIP 的视觉编码器，使用 `-1` 填充，并带有零注意力掩码），因此在训练和推理过程中，额外的图像插槽实际上被忽略了。

### 示例

XVLA-base 默认有三个视觉输入且 `empty_cameras=0`。如果你的数据集只有两个摄像头：

1. 设置 `--policy.empty_cameras=1`。
2. 配置将添加第三个键：`observation.images.empty_camera_0`。
3. 像往常一样为你的两个真实摄像头使用重命名映射。
4. 第三个插槽被掩码屏蔽 —— 你的数据集中不需要伪造图像。

## 快速参考

| 目标 | 场景 |
| --- | --- |
| 数据集键 ≠ 策略键 | `--rename_map='{"dataset_key": "policy_key", ...}'` |
| 环境键 ≠ 策略键 (评估) | `--rename_map='{"env_key": "policy_key", ...}'` |
| 使用不同键进行记录 (推理) | `--dataset.rename_map='{"source_key": "policy_key", ...}'`. |
| 摄像头数量少于策略期望 | `--policy.empty_cameras=N` (PI0, PI05, PI0Fast, SmolVLA, XVLA 支持) |
| 避免使用重命名映射 | 编辑策略的 `config.json` 使其键与你的数据源匹配 |

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/rename_map.mdx)
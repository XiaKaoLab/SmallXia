# 来源

https://hugging-face.cn/docs/lerobot/peft_training

# 使用 🤗 PEFT 进行参数高效微调

[🤗 PEFT](https://github.com/huggingface/peft) (Parameter-Efficient Fine-Tuning) 是一个用于高效适配大型预训练模型的库，例如预训练策略（如 SmolVLA, π₀ 等）。它可以在不训练模型全部参数的情况下将其适配到新任务，同时获得相当的性能。

安装 `lerobot[peft]` 可选软件包以启用 PEFT 支持。

如需阅读所有可能的适配方法，请参考 [🤗 PEFT 文档](https://hugging-face.cn/docs/peft/index)。

## 训练 SmolVLA

在本节中，我们将向您展示如何在 libero 数据集上使用 PEFT 训练预训练的 SmolVLA 策略。为了简洁，我们仅在 `libero_spatial` 子集上进行训练。我们将使用 `lerobot/smolvla_base` 作为参数高效微调的模型。

```
lerobot-train \
 --policy.path=lerobot/smolvla_base \
 --policy.repo_id=your_hub_name/my_libero_smolvla \
 --dataset.repo_id=HuggingFaceVLA/libero \
 --policy.output_features=null \
 --policy.input_features=null \
 --policy.optimizer_lr=1e-3 \
 --policy.scheduler_decay_lr=1e-4 \
 --env.type=libero \
 --env.task=libero_spatial \
 --steps=100000 \
 --batch_size=32 \
 --peft.method_type=LORA \
 --peft.r=64
```

请注意 `--peft.method_type` 参数，它允许您选择要使用的 PEFT 方法。这里我们使用 [LoRA](https://hugging-face.cn/docs/peft/main/en/package_reference/lora) (Low-Rank Adapter)，这可能是目前最受欢迎的微调方法。低秩适配意味着我们仅微调一个秩相对较低的矩阵，而不是完整的权重矩阵。该秩可以使用 `--peft.r` 参数指定。秩越高，越接近全参数微调。

还有一些包含更多参数的更复杂的方法。这些方法目前尚未支持，如果您希望支持某种特定的 PEFT 方法，请随时提交 issue。

默认情况下，PEFT 将针对 SmolVLA 中 LM 专家的 `q_proj` 和 `v_proj` 层。它还将针对状态和动作投影矩阵，因为它们最有可能依赖于具体任务。如果您需要针对不同的层，可以使用 `--peft.target_modules` 来指定目标层。您可以参考相应 PEFT 方法的文档以查看支持的输入（例如 [LoRA 的 target\_modules 文档](https://hugging-face.cn/docs/peft/main/en/package_reference/lora#peft.LoraConfig.target_modules)）。通常支持后缀列表或正则表达式。例如，要针对 `lm_expert` 的 MLP 而不是 `q` 和 `v` 投影，请使用

```
--peft.target_modules='(model\.vlm_with_expert\.lm_expert\..*\.(down|gate|up)_proj|.*\.(state_proj|action_in_proj|action_out_proj|action_time_mlp_in|action_time_mlp_out))'
```

如果您需要对某个层进行全参数微调而不是仅对其进行适配，可以在 `--peft.full_training_modules` 参数中提供层后缀列表。

```
--peft.full_training_modules=["state_proj"]
```

与全参数微调使用的学习率相比，学习率和计划的目标学习率通常可以放大 10 倍（例如，普通微调为 1e-4，使用 LoRA 则为 1e-3）。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/peft_training.mdx)
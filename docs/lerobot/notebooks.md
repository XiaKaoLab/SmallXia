# 来源

https://hugging-face.cn/docs/lerobot/notebooks

# 🤗 LeRobot Notebooks

本仓库包含使用 LeRobot 的示例 Notebook。这些 Notebook 展示了如何使用标准策略在真实或模拟数据集上训练策略。

---

### 训练 ACT

[ACT](https://hugging-face.cn/papers/2304.13705) (Action Chunking Transformer) 是一种基于 Transformer 的模仿学习策略架构，它处理机器人状态和摄像头输入，以生成平滑的分块动作序列。

我们提供了一个可直接运行的 Google Colab Notebook，帮助您使用来自 Hugging Face Hub 的数据集训练 ACT 策略，并可选地将日志记录到 Weights & Biases。

| 笔记本 | Colab |
| --- | --- |
| [使用 LeRobot 训练 ACT](https://github.com/huggingface/notebooks/blob/main/lerobot/training-act.ipynb) | [Open in Colab](https://colab.research.google.com/github/huggingface/notebooks/blob/main/lerobot/training-act.ipynb) |

10 万步的预期训练时间：在 NVIDIA A100 GPU 上，batch size 为 `64` 时约为 1.5 小时。

### 训练 SmolVLA

[SmolVLA](https://hugging-face.cn/papers/2506.01844) 是一个小型且高效的视觉-语言-动作 (Vision-Language-Action) 模型。它由 Hugging Face 开发，尺寸紧凑，拥有 4.5 亿 (450 M) 个参数。

我们提供了一个可直接运行的 Google Colab Notebook，帮助您使用来自 Hugging Face Hub 的数据集训练 SmolVLA 策略，并可选地将日志记录到 Weights & Biases。

| 笔记本 | Colab |
| --- | --- |
| [使用 LeRobot 训练 SmolVLA](https://github.com/huggingface/notebooks/blob/main/lerobot/training-smolvla.ipynb) | [Open in Colab](https://colab.research.google.com/github/huggingface/notebooks/blob/main/lerobot/training-smolvla.ipynb) |

2 万步的预期训练时间：在 NVIDIA A100 GPU 上，batch size 为 `64` 时约为 5 小时。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/notebooks.mdx)
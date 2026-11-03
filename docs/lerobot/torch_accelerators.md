# 来源

https://hugging-face.cn/docs/lerobot/torch_accelerators

# PyTorch 加速器

LeRobot 为训练和推理提供多种硬件加速选项。

这些选项包括：

* **CPU**：由 CPU 执行所有计算，不使用专用加速器
* **CUDA**：使用 NVIDIA 和 AMD GPU 进行加速
* **MPS**：使用 Apple Silicon GPU 进行加速
* **XPU**：使用 Intel 集成和独立 GPU 进行加速

## 入门

要使用特定的加速器，需要安装相应版本的 PyTorch。

对于 CPU、CUDA 和 MPS 后端，请参考 [PyTorch 安装页面](https://pytorch.ac.cn/get-started/locally)上提供的说明。对于 XPU 后端，请参考 [PyTorch 文档](https://docs.pytorch.ac.cn/docs/stable/notes/get_start_xpu.html)中的说明。

### 验证安装

安装完成后，可以通过运行以下命令来验证加速器的可用性：

```
import torch
print(torch.<backend_name>.is_available())  # <backend_name> is cuda, mps, or xpu
```

## 如何运行训练或评估

要选择所需的加速器，在运行 `lerobot-train` 或 `lerobot-eval` 时使用 `--policy.device` 标志。例如，要在 Apple Silicon 上使用 MPS，请运行：

```
lerobot-train
    --policy.device=mps ...
```

```
lerobot-eval \
    --policy.device=mps ...
```

不过，在大多数情况下，系统会自动检测加速器的存在，因此在 CLI 命令中可以省略 `policy.device` 参数。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/torch_accelerators.mdx)
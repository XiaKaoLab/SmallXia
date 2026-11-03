# 来源

https://hugging-face.cn/docs/lerobot/installation

# 安装

本指南使用 `conda` (通过 miniforge) 来管理环境（推荐）。如果您更倾向于使用其他环境管理器 (例如 `uv`, `venv`)，请确保您的 Python >=3.12 且支持 PyTorch >= 2.10，然后直接跳至 [环境设置](installation.md#step-2-environment-setup)。

## 步骤 1 (仅 conda): 安装 miniforge

```
wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
```

## 步骤 2: 环境设置

使用 Python 3.12 创建虚拟环境

conda

uv (仅限 PyTorch >= 2.10)

```
conda create -y -n lerobot python=3.12
```

然后激活您的虚拟环境，每次打开 shell 使用 lerobot 时都必须执行此操作

conda

uv (仅限 PyTorch >= 2.10)

```
conda activate lerobot
```

> 在 WSL (Windows Subsystem for Linux) 中安装 LeRobot 时，请确保同时安装 `evdev`
>
> ```
> conda install evdev -c conda-forge
> ```

### 安装 ffmpeg (用于视频解码)

LeRobot 默认使用 [TorchCodec](https://github.com/meta-pytorch/torchcodec) 进行视频解码，这需要安装 `ffmpeg`。

> **平台支持：** TorchCodec **不支持** macOS Intel (x86\_64)、Linux ARM (aarch64, arm64, armv7l) 或 PyTorch < 2.8 的 Windows。在这些平台上，LeRobot 会自动回退到 `pyav` —— 因此您不需要安装 `ffmpeg`，可以直接跳到步骤 3。

如果您的平台支持 TorchCodec，请使用以下方法之一安装 `ffmpeg`

conda (适用于任何 PyTorch 版本)

uv (仅限 PyTorch >= 2.10)

在您的 conda 环境中安装 `ffmpeg`。这适用于**所有 PyTorch 版本**，且对于 **PyTorch < 2.10 是必需的**

```
conda install ffmpeg -c conda-forge
```

> 这通常会安装带有 `libsvtav1` 编码器的 `ffmpeg 8.X`。如果您遇到问题（例如缺少 `libsvtav1` —— 请通过 `ffmpeg -encoders` 检查 —— 或与 `torchcodec` 版本不匹配），您可以使用以下命令明确安装 `ffmpeg 7.1.1`
>
> ```
> conda install ffmpeg=7.1.1 -c conda-forge
> ```

## 步骤 3: 安装 LeRobot 🤗

### 从源代码构建

首先，克隆仓库并进入该目录

```
git clone https://github.com/huggingface/lerobot.git
cd lerobot
```

然后，以可编辑模式安装库。如果您计划对代码做出贡献，这将非常有用。

conda

uv

```
pip install -e .
```

### 从 PyPI 安装

**核心库：** 使用以下命令安装基础包

conda

uv

```
pip install lerobot
```

*这将仅安装默认依赖项。*

**额外功能：** 要安装额外功能，请使用以下命令之一（如果您使用 `uv`，请将下方命令中的 `pip install` 替换为 `uv pip install`。）

```
pip install 'lerobot[all]'          # All available features
pip install 'lerobot[aloha,pusht]'  # Specific features (Aloha & Pusht)
pip install 'lerobot[feetech]'      # Feetech motor support
```

*将 `[...]` 替换为您需要的功能。*

**可用标签：** 有关可选依赖项的完整列表，请参阅：<https://pypi.ac.cn/project/lerobot/>

### 疑难解答

如果您遇到构建错误，可能需要安装额外的依赖项：`cmake`, `build-essential` 和 `ffmpeg libs`。在 Linux 上安装这些项请运行

```
sudo apt-get install cmake build-essential python3-dev pkg-config libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev
```

对于其他系统，请参阅：[编译 PyAV](https://pyav.org/docs/develop/overview/installation.html#bring-your-own-ffmpeg)

## 可选依赖项

LeRobot 为特定功能提供了可选的额外组件。可以将多个组件组合在一起 (例如 `.[aloha,feetech]`)。所有可用组件请参考 `pyproject.toml`。如果您使用 `uv`，请将下方命令中的 `pip install` 替换为 `uv pip install`。

### 模拟

安装环境包：`aloha` ([gym-aloha](https://github.com/huggingface/gym-aloha)) 或 `pusht` ([gym-pusht](https://github.com/huggingface/gym-pusht)) 示例

```
pip install -e ".[aloha]" # or "[pusht]" for example
```

### 电机控制

对于 Koch v1.1，请安装 Dynamixel SDK；对于 SO100/SO101/Moss，请安装 Feetech SDK。

```
pip install -e ".[feetech]" # or "[dynamixel]" for example
```

### 实验追踪

要使用 [Weights and Biases](https://docs.wandb.ai/quickstart) 进行实验追踪，请使用以下账号登录：

```
wandb login
```

如果您的机器人尚未准备好，现在可以开始组装；在左侧查找您的机器人类型。然后点击下方链接，将 LeRobot 应用于您的机器人。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/installation.mdx)
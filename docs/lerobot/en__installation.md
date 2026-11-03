# 来源

https://hugging-face.cn/docs/lerobot/en/installation

# Installation

This guide uses `conda` (via miniforge) to manage environments (recommended). If you prefer another environment manager (e.g. `uv`, `venv`), ensure you have Python >=3.12 and support PyTorch >= 2.10, then skip ahead to [Environment Setup](en__installation.md#step-2-environment-setup).

## Step 1 ( conda only): Install miniforge

```
wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
```

 

## Step 2: Environment Setup

Create a virtual environment with Python 3.12:

conda

uv (PyTorch >= 2.10 only)

```
conda create -y -n lerobot python=3.12
```

Then activate your virtual environment, you have to do this each time you open a shell to use lerobot:

conda

uv (PyTorch >= 2.10 only)

```
conda activate lerobot
```

> When installing LeRobot inside WSL (Windows Subsystem for Linux), make sure to also install `evdev`:
>
> ```
> conda install evdev -c conda-forge
> ```

 

### Install ffmpeg (for video decoding)

LeRobot uses [TorchCodec](https://github.com/meta-pytorch/torchcodec) for video decoding by default, which requires `ffmpeg`.

> **Platform support:** TorchCodec is **not available** on macOS Intel (x86\_64), Linux ARM (aarch64, arm64, armv7l), or Windows with PyTorch < 2.8. On these platforms, LeRobot automatically falls back to `pyav` — so you do not need to install `ffmpeg` and can skip to Step 3.

If your platform supports TorchCodec, install `ffmpeg` using one of the methods below:

conda (any PyTorch version)

uv (PyTorch >= 2.10 only)

Install `ffmpeg` in your conda environment. This works with **all PyTorch versions** and is **required for PyTorch < 2.10**:

```
conda install ffmpeg -c conda-forge
```

> This usually installs `ffmpeg 8.X` with the `libsvtav1` encoder. If you run into issues (e.g. `libsvtav1` missing — check with `ffmpeg -encoders` — or a version mismatch with `torchcodec`), you can explicitly install `ffmpeg 7.1.1` using:
>
> ```
> conda install ffmpeg=7.1.1 -c conda-forge
> ```

 

## Step 3: Install LeRobot 🤗

The base `lerobot` install is intentionally **lightweight** — it includes only core ML dependencies (PyTorch, torchvision, numpy, opencv, einops, draccus, huggingface-hub, gymnasium, safetensors). Heavier dependencies are gated behind optional extras so you only install what you need.

### From Source

First, clone the repository and navigate into the directory:

```
git clone https://github.com/huggingface/lerobot.git
cd lerobot
```

Then, install the library in editable mode. This is useful if you plan to contribute to the code.

conda

uv

```
pip install -e ".[core_scripts]"  # For robot workflows (recording, replaying, calibrate)
pip install -e ".[training]"      # For training policies
pip install -e ".[all]"           # Everything (all policies, envs, hardware, dev tools)
```

 

### Installation from PyPI

**Core Library:** Install the base package with:

conda

uv

```
pip install lerobot
```

*This installs only the core ML dependencies. You will need to add extras for most workflows.*

**Feature Extras:** LeRobot provides **feature-scoped extras** that map to common workflows. If you are using `uv`, replace `pip install` with `uv pip install` in the commands below.

| Extra | What it adds | Typical use case |
| --- | --- | --- |
| `dataset` | `datasets`, `av`, `torchcodec`, `jsonlines` | Loading & creating datasets |
| `training` | `dataset` + `accelerate`, `wandb` | Training policies |
| `hardware` | `pynput`, `pyserial`, `deepdiff` | Connecting to real robots |
| `viz` | `rerun-sdk` | Visualization during recording/eval |

**Composite Extras** combine feature extras for common CLI scripts:

| Extra | Includes | Typical use case |
| --- | --- | --- |
| `core_scripts` | `dataset` + `hardware` + `viz` | `lerobot-record`, `lerobot-replay`, `lerobot-calibrate` |
| `evaluation` | `av` | `lerobot-eval` (add policy + env extras as needed) |
| `dataset_viz` | `dataset` + `viz` | `lerobot-dataset-viz`, `lerobot-imgtransform-viz` |

```
pip install 'lerobot[core_scripts]'          # Record, replay, calibrate
pip install 'lerobot[training]'              # Train policies
pip install 'lerobot[core_scripts,training]' # Record + train
pip install 'lerobot[all]'                   # Everything
```

**Policy, environment, and hardware extras** are still available for specific dependencies:

```
pip install 'lerobot[pi]'             # Pi0/Pi0.5/Pi0-FAST policy deps
pip install 'lerobot[smolvla]'        # SmolVLA policy deps
pip install 'lerobot[diffusion]'      # Diffusion policy deps (diffusers)
pip install 'lerobot[aloha,pusht]'    # Simulation environments
pip install 'lerobot[feetech]'        # Feetech motor support
```

*Multiple extras can be combined (e.g., `.[core_scripts,pi,pusht]`). For a full list of available extras, refer to `pyproject.toml`.*

### PyTorch CUDA variant (Linux only)

On Linux, the install path determines which CUDA wheel you get. macOS and Windows installs use the PyPI default (MPS / CPU / CUDA-Windows wheel respectively) and can skip this section.

uv-source

pip-conda

**Source install via `uv` (`uv sync` or `uv pip install -e .`)**

`torch` and `torchvision` are pinned by the project to the **CUDA 12.8** PyTorch index (`https://download.pytorch.org/whl/cu128`, driver floor **570.86**) — covers Ampere/Ada/Hopper/Blackwell GPUs. No action needed for typical NVIDIA setups.

To override for a different CUDA variant:

```
uv pip install --force-reinstall torch torchvision \
    --index-url https://download.pytorch.org/whl/cu126   # older drivers; or cu130 for Blackwell on driver ≥ 580
```

 

### Troubleshooting

If you encounter build errors, you may need to install additional system dependencies: `cmake`, `build-essential`, and `ffmpeg libs`.
To install these for Linux run:

```
sudo apt-get install cmake build-essential python3-dev pkg-config libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev
```

For other systems, see: [Compiling PyAV](https://pyav.org/docs/develop/overview/installation.html#bring-your-own-ffmpeg)

## Optional dependencies

LeRobot provides optional extras for specific functionalities. Multiple extras can be combined (e.g., `.[aloha,feetech]`). For all available extras, refer to `pyproject.toml`. If you are using `uv`, replace `pip install` with `uv pip install` in the commands below.

### Simulations

Install environment packages: `aloha` ([gym-aloha](https://github.com/huggingface/gym-aloha)), or `pusht` ([gym-pusht](https://github.com/huggingface/gym-pusht)).
These automatically include the `dataset` extra.

```
pip install -e ".[aloha]" # or "[pusht]" for example
```

 

### Motor Control

For Koch v1.1 install the Dynamixel SDK, for SO100/SO101/Moss install the Feetech SDK.

```
pip install -e ".[feetech]" # or "[dynamixel]" for example
```

 

### Experiment Tracking

Weights and Biases is included in the `training` extra. To use [Weights and Biases](https://docs.wandb.ai/quickstart) for experiment tracking, log in with:

```
wandb login
```

You can now assemble your robot if it’s not ready yet, look for your robot type on the left. Then follow the link below to use Lerobot with your robot.

 [Update on GitHub](https://github.com/huggingface/lerobot/blob/main/docs/source/installation.mdx)
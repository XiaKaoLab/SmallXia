# 来源

https://hugging-face.cn/docs/lerobot/envhub_isaaclab_arena

# NVIDIA IsaacLab Arena & LeRobot

LeRobot EnvHub 现在支持通过 IsaacLab Arena 进行 **GPU 加速仿真**，以实现大规模的策略评估。在 LeRobot 生态系统中，您可以进行高保真仿真训练和评估模仿学习策略。

![IsaacLab Arena - GR1 Microwave Environment](https://hugging-face.cn/nvidia/isaaclab-arena-envs/resolve/main/assets/Gr1OpenMicrowaveEnvironment.png)

[IsaacLab Arena](https://github.com/isaac-sim/IsaacLab-Arena) 与 NVIDIA IsaacLab 集成，提供：

* 🤖 **人形机器人本体**：包含各种配置的 GR1, G1, Galileo
* 🎯 **操作与移动操作任务**：开门、取放物品、按按钮等
* ⚡ **GPU 加速推演**：在 NVIDIA GPU 上进行并行环境执行
* 🖼️ **RTX 渲染**：通过包含真实反射和折射的逼真渲染效果，评估基于视觉的策略
* 📦 **兼容 LeRobot 的数据集**：可直接用于训练 GR00T N1x, PI0, SmolVLA, ACT 和 Diffusion 策略
* 🔄 **EnvHub 集成**：仅需一行代码即可从 HuggingFace EnvHub 加载环境

## 安装

### 先决条件

硬件要求与 Isaac Sim 相同，详见 [Isaac Sim 要求](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html)。

* 支持 CUDA 的 NVIDIA GPU
* 兼容 IsaacSim 5.1.0 的 NVIDIA 驱动程序
* Linux (Ubuntu 22.04 / 24.04)

### 设置

```
# 1. Create conda environment
conda create -y -n lerobot-arena python=3.11
conda activate lerobot-arena
conda install -y -c conda-forge ffmpeg=7.1.1

# 2. Install Isaac Sim 5.1.0
pip install "isaacsim[all,extscache]==5.1.0" --extra-index-url https://pypi.nvidia.com

# Accept NVIDIA EULA (required)
export ACCEPT_EULA=Y
export PRIVACY_CONSENT=Y

# 3. Install IsaacLab 2.3.0
git clone https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab
git checkout v2.3.0
./isaaclab.sh -i
cd ..

# 4. Install IsaacLab Arena
git clone https://github.com/isaac-sim/IsaacLab-Arena.git
cd IsaacLab-Arena
git checkout release/0.1.1
pip install -e .
cd ..


# 5. Install LeRobot
git clone https://github.com/huggingface/lerobot.git
cd lerobot
pip install -e .
cd ..


# 6. Install additional dependencies
pip install onnxruntime==1.23.2 lightwheel-sdk==1.0.1 vuer[all]==0.0.70 qpsolvers==4.8.1
pip install numpy==1.26.0 # Isaac Sim 5.1 depends on numpy==1.26.0, this will be fixed in next release
```

## 策略评估

### 预训练策略

提供以下已训练策略

| 策略 | 架构 | 任务 | 链接 |
| --- | --- | --- | --- |
| pi05-arena-gr1-microwave | PI0.5 | GR1 微波炉任务 | [HuggingFace](https://hugging-face.cn/nvidia/pi05-arena-gr1-microwave) |
| smolvla-arena-gr1-microwave | SmolVLA | GR1 微波炉任务 | [HuggingFace](https://hugging-face.cn/nvidia/smolvla-arena-gr1-microwave) |

### 评估 SmolVLA

```
pip install -e ".[smolvla]"
pip install numpy==1.26.0 # revert numpy to version 1.26
```

```
lerobot-eval \
    --policy.path=nvidia/smolvla-arena-gr1-microwave \
    --env.type=isaaclab_arena \
    --env.hub_path=nvidia/isaaclab-arena-envs \
    --rename_map='{"observation.images.robot_pov_cam_rgb": "observation.images.robot_pov_cam"}' \
    --policy.device=cuda \
    --env.environment=gr1_microwave \
    --env.embodiment=gr1_pink \
    --env.object=mustard_bottle \
    --env.headless=false \
    --env.enable_cameras=true \
    --env.video=true \
    --env.video_length=10 \
    --env.video_interval=15 \
    --env.state_keys=robot_joint_pos \
    --env.camera_keys=robot_pov_cam_rgb \
    --trust_remote_code=True \
    --eval.batch_size=1
```

### 评估 PI0.5

```
pip install -e ".[pi]"
pip install numpy==1.26.0 # revert numpy to version 1.26
```

> PI0.5 评估时需要禁用 torch compile

```
TORCH_COMPILE_DISABLE=1 TORCHINDUCTOR_DISABLE=1 lerobot-eval \
    --policy.path=nvidia/pi05-arena-gr1-microwave \
    --env.type=isaaclab_arena \
    --env.hub_path=nvidia/isaaclab-arena-envs \
    --rename_map='{"observation.images.robot_pov_cam_rgb": "observation.images.robot_pov_cam"}' \
    --policy.device=cuda \
    --env.environment=gr1_microwave \
    --env.embodiment=gr1_pink \
    --env.object=mustard_bottle \
    --env.headless=false \
    --env.enable_cameras=true \
    --env.video=true \
    --env.video_length=15 \
    --env.video_interval=15 \
    --env.state_keys=robot_joint_pos \
    --env.camera_keys=robot_pov_cam_rgb \
    --trust_remote_code=True \
    --eval.batch_size=1
```

> 如需更改并行环境的数量，请使用 ```--eval.batch\_size``` 标志。

### 预期结果

在评估过程中，您将看到显示实时成功率的进度条

```
Stepping through eval batches:   8%|██████▍    | 4/50 [00:45<08:06, 10.58s/it, running_success_rate=25.0%]
```

### 录制视频

如需在评估期间开启录制，请在命令中添加以下标志

```
--env.video=true \
--env.video_length=15 \
--env.video_interval=15
```

有关视频录制的更多详情，请参阅 [IsaacLab 录制文档](https://isaac-sim.github.io/IsaacLab/main/source/how-to/record_video.html)。

> 当使用 `--env.headless=true` 运行无头模式时，对于开启相机的环境，您还必须显式开启相机
>
> ```
> --env.headless=true --env.enable_cameras=true
> ```

### 输出目录

评估视频将保存到输出目录，结构如下

```
outputs/eval/<date>/<timestamp>_<env>_<policy>/videos/<task>_<env_id>/eval_episode_<n>.mp4
```

例如：

```
outputs/eval/2026-01-02/14-38-01_isaaclab_arena_smolvla/videos/gr1_microwave_0/eval_episode_0.mp4
```

## 训练策略

欲了解更多有关使用 LeRobot 训练策略的信息，请参考训练文档

* [SmolVLA](smolvla.md)
* [Pi0.5](pi05.md)
* [GR00T N1.5](groot.md)

HuggingFace Hub 上提供了 IsaacLab Arena 示例数据集供实验使用

| 数据集 | 描述 | 帧 |
| --- | --- | --- |
| [Arena-GR1-操作任务](https://hugging-face.cn/datasets/nvidia/Arena-GR1-Manipulation-Task-v3) | GR1 微波炉操作 | ~4K |
| [Arena-G1-移动操作任务](https://hugging-face.cn/datasets/nvidia/Arena-G1-Loco-Manipulation-Task) | G1 移动操作 | ~4K |

## 环境配置

### 完整配置选项

```
from lerobot.envs.configs import IsaaclabArenaEnv

config = IsaaclabArenaEnv(
    # Environment selection
    environment="gr1_microwave",      # Task environment
    embodiment="gr1_pink",            # Robot embodiment
    object="power_drill",             # Object to manipulate

    # Simulation settings
    episode_length=300,               # Max steps per episode
    headless=True,                    # Run without GUI
    device="cuda:0",                  # GPU device
    seed=42,                          # Random seed

    # Observation configuration
    state_keys="robot_joint_pos",     # State observation keys (comma-separated)
    camera_keys="robot_pov_cam_rgb",  # Camera observation keys (comma-separated)
    state_dim=54,                     # Expected state dimension
    action_dim=36,                    # Expected action dimension
    camera_height=512,                # Camera image height
    camera_width=512,                 # Camera image width
    enable_cameras=True,              # Enable camera observations

    # Video recording
    video=False,                      # Enable video recording
    video_length=100,                 # Frames per video
    video_interval=200,               # Steps between recordings

    # Advanced
    mimic=False,                      # Enable mimic mode
    teleop_device=None,               # Teleoperation device
    disable_fabric=False,             # Disable fabric optimization
    enable_pinocchio=True,            # Enable Pinocchio for IK
)
```

### 直接使用 Environment Hub（高级用法）

创建一个名为 `test_env_load_arena.py` 的文件，或者[从 EnvHub 下载](https://hugging-face.cn/nvidia/isaaclab-arena-envs/blob/main/tests/test_env_load_arena.py)

```
import logging
from dataclasses import asdict
from pprint import pformat
import torch
import tqdm
from lerobot.configs import parser
from lerobot.configs.eval import EvalPipelineConfig


@parser.wrap()
def main(cfg: EvalPipelineConfig):
    """Run random action rollout for IsaacLab Arena environment."""
    logging.info(pformat(asdict(cfg)))

    from lerobot.envs.factory import make_env

    env_dict = make_env(
        cfg.env,
        n_envs=cfg.env.num_envs,
        trust_remote_code=True,
    )
    env = next(iter(env_dict.values()))[0]
    env.reset()
    for _ in tqdm.tqdm(range(cfg.env.episode_length)):
        with torch.inference_mode():
            actions = env.action_space.sample()
            obs, rewards, terminated, truncated, info = env.step(actions)
            if terminated.any() or truncated.any():
                obs, info = env.reset()
    env.close()


if __name__ == "__main__":
    main()
```

运行命令

```
python test_env_load_arena.py \
    --env.environment=g1_locomanip_pnp \
    --env.embodiment=gr1_pink \
    --env.object=cracker_box \
    --env.num_envs=4 \
    --env.enable_cameras=true \
    --env.seed=1000 \
    --env.video=true \
    --env.video_length=10 \
    --env.video_interval=15 \
    --env.headless=false \
    --env.hub_path=nvidia/isaaclab-arena-envs \
    --env.type=isaaclab_arena
```

## 创建新环境

首先，请按照 [IsaacLab Arena 文档](https://isaac-sim.github.io/IsaacLab-Arena/release/0.1.1/index.html) 创建一个新的 IsaacLab Arena 环境。

克隆我们的 EnvHub 仓库

```
git clone https://hugging-face.cn/nvidia/isaaclab-arena-envs
```

根据新环境修改 `example_envs.yaml` 文件。[上传](envhub.md#step-3-upload-to-the-hub) 修改后的仓库至 HuggingFace EnvHub。

> 在评估期间，您的 IsaacLab Arena 环境代码必须在本地可用。用户可以单独克隆您的环境仓库，或者您可以直接将环境代码和资产打包到您的 EnvHub 仓库中。

随后，在评估时，请使用您的新环境

```
lerobot-eval \
    --env.hub_path=<your-env-hub-path>/isaaclab-arena-envs \
    --env.environment=<your new environment> \
    ...other flags...
```

我们期待您的贡献！

## 疑难解答

### CUDA 显存溢出 (out of memory)

减小 `batch_size` 或使用具有更多显存 (VRAM) 的 GPU

```
--eval.batch_size=1
```

### 未接受 EULA

运行前设置环境变量

```
export ACCEPT_EULA=Y
export PRIVACY_CONSENT=Y
```

### 视频录制不工作

在无头模式下运行时启用相机

```
--env.video=true --env.enable_cameras=true --env.headless=true
```

### 策略输出维度不匹配

确保 `action_dim` 与您的策略相匹配

```
--env.action_dim=36
```

### Isaac Sim 初始化期间出现 libGLU.so.1 错误

请确保安装了以下依赖项，此类错误通常发生在无头机器（Headless machine）上。

```
sudo apt update && sudo apt install -y libglu1-mesa libxt6
```

## 参见

* [EnvHub 文档](https://hugging-face.cn/docs/lerobot/envhub.mdx) - 常规 EnvHub 用法
* [IsaacLab Arena GitHub](https://github.com/isaac-sim/IsaacLab-Arena)
* [IsaacLab 文档](https://isaac-sim.github.io/IsaacLab/)

## Lightwheel LW-BenchHub

[Lightwheel](https://www.lightwheel.ai) 正在为 LeRobot 生态系统带来 `Lightwheel-Libero-Tasks` 和 `Lightwheel-RoboCasa-Tasks`，共包含 268 个任务。LW-BenchHub 通过远程操作收集并生成符合 LeRobot 规范的大规模数据集，从而实现开箱即用的训练和评估工作流。凭借 EnvHub 提供的统一接口，开发者可以快速构建端到端的实验流水线。

### 安装

假设您已完成 [安装](envhub_isaaclab_arena.md#installation) 步骤，您可以通过以下命令安装 LW-BenchHub：

```
conda install pinocchio -c conda-forge -y
pip install numpy==1.26.0 # revert numpy to version 1.26

sudo apt-get install git-lfs && git lfs install

git clone https://github.com/LightwheelAI/lw_benchhub
git lfs pull # Ensure LFS files (e.g., .usd assets) are downloaded

cd lw_benchhub
pip install -e .
```

更详细的说明请参考 [LW-BenchHub 文档](https://docs.lightwheel.net/lw_benchhub/usage/Installation)。

### Lightwheel 任务数据集

LW-BenchHub 数据集已在 HuggingFace Hub 上发布

| 数据集 | 描述 | 任务 | 帧 |
| --- | --- | --- | --- |
| [Lightwheel-Tasks-X7S](https://hugging-face.cn/datasets/LightwheelAI/Lightwheel-Tasks-X7S) | X7S LIBERO 和 RoboCasa | 117 | ~10.3M |
| [Lightwheel-Tasks-Double-Piper](https://hugging-face.cn/datasets/LightwheelAI/Lightwheel-Tasks-Double-Piper) | Double-Piper LIBERO | 130 | ~6.0M |
| [Lightwheel-Tasks-G1-Controller](https://hugging-face.cn/datasets/LightwheelAI/Lightwheel-Tasks-G1-Controller) | G1-Controller LIBERO | 62 | ~2.7M |
| [Lightwheel-Tasks-G1-WBC](https://hugging-face.cn/datasets/LightwheelAI/Lightwheel-Tasks-G1-WBC) | G1-WBC RoboCasa | 32 | ~1.5M |

如需训练策略，请参考 [训练策略](envhub_isaaclab_arena.md#training-policies) 部分。

### 策略评估

#### 预训练策略

提供以下已训练策略

| 策略 | 架构 | 任务 | 布局 | 机器人 | 链接 |
| --- | --- | --- | --- | --- | --- |
| smolvla-double-piper-pnp | SmolVLA | L90K1PutTheBlackBowlOnThePlate | libero-1-1 | DoublePiper-Abs | [HuggingFace](https://hugging-face.cn/LightwheelAI/smolvla-double-piper-pnp/tree/main) |

#### 评估 SmolVLA

```
lerobot-eval \
  --policy.path=LightwheelAI/smolvla-double-piper-pnp \
  --env.type=isaaclab_arena \
  --rename_map='{"observation.images.left_hand_camera_rgb": "observation.images.left_hand", "observation.images.right_hand_camera_rgb": "observation.images.right_hand", "observation.images.first_person_camera_rgb": "observation.images.first_person"}' \
  --env.hub_path=LightwheelAI/lw_benchhub_env \
  --env.kwargs='{"config_path": "configs/envhub/example.yml"}' \
  --trust_remote_code=true \
  --env.state_keys=joint_pos \
  --env.action_dim=12 \
  --env.camera_keys=left_hand_camera_rgb,right_hand_camera_rgb,first_person_camera_rgb \
  --policy.device=cuda \
  --eval.batch_size=10 \
  --eval.n_episodes=100
```

### 环境配置

通过修改配置文件中的 `robot`、`task` 和 `layout` 设置，可以快速启动评估。

#### 完整配置选项

```
# =========================
# Basic Settings
# =========================
disable_fabric: false
device: cuda:0
sensitivity: 1.0
step_hz: 50
enable_cameras: true
execute_mode: eval
episode_length_s: 20.0 # Episode length in seconds, increase if episodes timeout during eval

# =========================
# Robot Settings
# =========================
robot: DoublePiper-Abs # Robot type, DoublePiper-Abs, X7S-Abs, G1-Controller or G1-Controller-DecoupledWBC
robot_scale: 1.0

# =========================
# Task & Scene Settings
# =========================
task: L90K1PutTheBlackBowlOnThePlate # Task name
scene_backend: robocasa
task_backend: robocasa
debug_assets: null
layout: libero-1-1 # Layout and style ID
sources:
  - objaverse
  - lightwheel
  - aigen_objs
object_projects: []
usd_simplify: false
seed: 42

# =========================
# Object Placement Retry Settings
# =========================
max_scene_retry: 4
max_object_placement_retry: 3

resample_objects_placement_on_reset: true
resample_robot_placement_on_reset: true

# =========================
# Replay Configuration Settings
# =========================
replay_cfgs:
  add_camera_to_observation: true
  render_resolution: [640, 480]
```

### 参见

* [LW-BenchHub GitHub](https://github.com/LightwheelAI/LW-BenchHub)
* [LW-BenchHub 文档](https://docs.lightwheel.net/lw_benchhub/)

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/envhub_isaaclab_arena.mdx)
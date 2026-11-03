# 来源

https://hugging-face.cn/docs/lerobot/envhub_leisaac

# LeIsaac × LeRobot EnvHub

LeRobot EnvHub 现在支持通过 LeIsaac 在**仿真环境中进行模仿学习**。您可以启动日常操作任务、遥操作机器人、收集演示数据、将其推送到 Hub，并在 LeRobot 中训练策略 —— 全部在同一个闭环中完成。

[LeIsaac](https://github.com/LightwheelAI/leisaac) 与 IsaacLab 及 SO101 主从架构（Leader/Follower）集成，提供：

* 🕹️ **以遥操作为核心的工作流**，用于数据收集
* 📦 **内置数据转换**，可直接用于 LeRobot 训练
* 🤖 **日常技能**，如采摘橙子、举起方块、清理桌面和折叠衣服
* ☁️ **来自 [LightWheel](https://lightwheel.ai/) 的持续升级**：云端仿真、EnvHub 支持、Sim2Real 工具等

以下是目前通过 LeRobot EnvHub 提供的 LeIsaac 支持任务。

# 可用环境

下表列出了 LeIsaac x LeRobot Envhub 中所有可用的任务和环境。您也可以通过运行以下命令获取最新的环境列表

```
python scripts/environments/list_envs.py
```

| 任务 | 环境 ID | 任务描述 | 相关机器人 |
| --- | --- | --- | --- |
|  | [LeIsaac-SO101-PickOrange-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/pick_orange/pick_orange_env_cfg.py)  [LeIsaac-SO101-PickOrange-Direct-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/pick_orange/direct/pick_orange_env.py) | 采摘三个橙子并放入盘中，然后将机械臂复位到静止状态。 | 单臂 SO101 Follower |
|  | [LeIsaac-SO101-LiftCube-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/lift_cube/lift_cube_env_cfg.py)  [LeIsaac-SO101-LiftCube-Direct-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/lift_cube/direct/lift_cube_env.py) | 举起红色方块。 | 单臂 SO101 Follower |
|  | [LeIsaac-SO101-CleanToyTable-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/clean_toy_table/clean_toy_table_env_cfg.py)  [LeIsaac-SO101-CleanToyTable-BiArm-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/clean_toy_table/clean_toy_table_bi_arm_env_cfg.py)  [LeIsaac-SO101-CleanToyTable-BiArm-Direct-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/clean_toy_table/direct/clean_toy_table_bi_arm_env.py) | 将两个字母 e 物体放入盒子中，然后将机械臂复位到静止状态。 | 单臂 SO101 Follower  双臂 SO101 Follower |
|  | [LeIsaac-SO101-FoldCloth-BiArm-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/fold_cloth/fold_cloth_bi_arm_env_cfg.py)  [LeIsaac-SO101-FoldCloth-BiArm-Direct-v0](https://github.com/LightwheelAI/leisaac/blob/main/source/leisaac/leisaac/tasks/fold_cloth/direct/fold_cloth_bi_arm_env.py) | 折叠衣服，然后将机械臂复位到静止状态。  *注意：在该任务中，仅 DirectEnv 支持 check\_success。* | 双臂 SO101 Follower |

# 使用一行代码在 LeRobot 中直接加载 LeIsaac

> EnvHub：通过 HuggingFace 分享 LeIsaac 环境

[EnvHub](envhub.md) 是我们的可复现环境中心。您可以用一行代码启动一个打包好的仿真环境，立即进行实验，并为社区发布您自己的任务。

LeIsaac 提供了 EnvHub 支持，因此您只需几个命令即可使用或分享任务。

[](https://github.com/user-attachments/assets/687666f5-ebe0-421d-84a0-eb86116ac5f8)

## 如何入门，环境搭建

运行以下命令来搭建您的代码环境

```
# Refer to Getting Started/Installation to install leisaac firstly
conda create -n leisaac_envhub python=3.11
conda activate leisaac_envhub

conda install -c "nvidia/label/cuda-12.8.1" cuda-toolkit
pip install -U torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cu128
pip install 'leisaac[isaaclab] @ git+https://github.com/LightwheelAI/leisaac.git#subdirectory=source/leisaac' --extra-index-url https://pypi.nvidia.com

# Install lerobot
pip install lerobot==0.4.1

# Fix numpy version
pip install numpy==1.26.0
```

## 用法示例

EnvHub 通过统一的接口公开了所有 LeIsaac 支持的任务。下面的示例加载了 `so101_pick_orange`，并演示了随机动作滚动（random-action rollout）和交互式遥操作。

### 随机动作

点击展开代码示例

```
# envhub_random_action.py

import torch
from lerobot.envs.factory import make_env

# Load from the hub
envs_dict = make_env("LightwheelAI/leisaac_env:envs/so101_pick_orange.py", n_envs=1, trust_remote_code=True)

# Access the environment
suite_name = next(iter(envs_dict))
sync_vector_env = envs_dict[suite_name][0]
# retrieve the isaac environment from the sync vector env
env = sync_vector_env.envs[0].unwrapped

# Use it like any gym environment
obs, info = env.reset()

while True:
    action = torch.tensor(env.action_space.sample())
    obs, reward, terminated, truncated, info = env.step(action)
    if terminated or truncated:
        obs, info = env.reset()

env.close()
```

```
python envhub_random_action.py
```

您应该能看到 SO101 机械臂在纯随机命令下摆动。

### 遥操作

LeRobot 的遥操作栈可以驱动仿真机械臂。

连接 SO101 Leader 控制器，运行下面的校准命令。

```
lerobot-calibrate \
    --teleop.type=so101_leader \
    --teleop.port=/dev/ttyACM0 \
    --teleop.id=leader
```

然后启动遥操作脚本。

点击展开代码示例

```
# envhub_teleop_example.py

import logging
import time
import gymnasium as gym

from dataclasses import asdict, dataclass
from pprint import pformat

from lerobot.teleoperators import (  # noqa: F401
    Teleoperator,
    TeleoperatorConfig,
    make_teleoperator_from_config,
    so_leader,
    bi_so_leader,
)
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import init_logging
from lerobot.envs.factory import make_env


@dataclass
class TeleoperateConfig:
    teleop: TeleoperatorConfig
    env_name: str = "so101_pick_orange"
    fps: int = 60


@dataclass
class EnvWrap:
    env: gym.Env


def make_env_from_leisaac(env_name: str = "so101_pick_orange"):
    envs_dict = make_env(
        f'LightwheelAI/leisaac_env:envs/{env_name}.py',
        n_envs=1,
        trust_remote_code=True
    )
    suite_name = next(iter(envs_dict))
    sync_vector_env = envs_dict[suite_name][0]
    env = sync_vector_env.envs[0].unwrapped

    return env


def teleop_loop(teleop: Teleoperator, env: gym.Env, fps: int):
    from leisaac.devices.action_process import preprocess_device_action
    from leisaac.assets.robots.lerobot import SO101_FOLLOWER_MOTOR_LIMITS
    from leisaac.utils.env_utils import dynamic_reset_gripper_effort_limit_sim

    env_wrap = EnvWrap(env=env)

    obs, info = env.reset()
    while True:
        loop_start = time.perf_counter()
        if env.cfg.dynamic_reset_gripper_effort_limit:
            dynamic_reset_gripper_effort_limit_sim(env, 'so101leader')

        raw_action = teleop.get_action()
        processed_action = preprocess_device_action(
            dict(
                so101_leader=True,
                joint_state={
                    k.removesuffix(".pos"): v for k, v in raw_action.items()},
                motor_limits=SO101_FOLLOWER_MOTOR_LIMITS),
            env_wrap
        )
        obs, reward, terminated, truncated, info = env.step(processed_action)
        if terminated or truncated:
            obs, info = env.reset()

        dt_s = time.perf_counter() - loop_start
        precise_sleep(max(1 / fps - dt_s, 0.0))
        loop_s = time.perf_counter() - loop_start
        print(f"\ntime: {loop_s * 1e3:.2f}ms ({1 / loop_s:.0f} Hz)")


def teleoperate(cfg: TeleoperateConfig):
    init_logging()
    logging.info(pformat(asdict(cfg)))

    teleop = make_teleoperator_from_config(cfg.teleop)
    env = make_env_from_leisaac(cfg.env_name)

    teleop.connect()
    if hasattr(env, 'initialize'):
        env.initialize()
    try:
        teleop_loop(teleop=teleop, env=env, fps=cfg.fps)
    except KeyboardInterrupt:
        pass
    finally:
        teleop.disconnect()
        env.close()


def main():
    teleoperate(TeleoperateConfig(
        teleop=so_leader.SO101LeaderConfig(
            port="/dev/ttyACM0",
            id='leader',
            use_degrees=False,
        ),
        env_name="so101_pick_orange",
        fps=60,
    ))


if __name__ == "__main__":
    main()
```

```
python envhub_teleop_example.py
```

运行该脚本后，您可以使用物理 Leader 设备来操作仿真机械臂。

## ☁️ 云端仿真（无需 GPU）

没有本地 GPU 或正确的驱动程序？没问题！您可以在云端完全运行 LeIsaac，无需任何设置。LeIsaac 在 **NVIDIA Brev** 上开箱即用，直接在浏览器中为您提供完整配置的环境。

👉 **由此开始：** <https://lightwheelai.github.io/leisaac/docs/cloud_simulation/nvidia_brev>

实例部署后，只需打开 **80 端口 (HTTP)** 的链接即可启动 **Visual Studio Code Server**（默认密码：`password`）。从此，您可以在 Web 浏览器中运行仿真、编辑代码并可视化 IsaacLab 环境。

**无需 GPU，无需驱动，无需本地安装。只需点击即可运行。**

## 补充说明

我们使 EnvHub 的覆盖范围与 LeIsaac 任务保持一致。目前支持：

* `so101_pick_orange`
* `so101_lift_cube`
* `so101_clean_toytable`
* `bi_so101_fold_cloth`

在调用 `make_env` 时指定不同的脚本即可切换任务，例如：

```
envs_dict_pick_orange = make_env("LightwheelAI/leisaac_env:envs/so101_pick_orange.py", n_envs=1, trust_remote_code=True)
envs_dict_lift_cube = make_env("LightwheelAI/leisaac_env:envs/so101_lift_cube.py", n_envs=1, trust_remote_code=True)
envs_dict_clean_toytable = make_env("LightwheelAI/leisaac_env:envs/so101_clean_toytable.py", n_envs=1, trust_remote_code=True)
envs_dict_fold_cloth = make_env("LightwheelAI/leisaac_env:envs/bi_so101_fold_cloth.py", n_envs=1, trust_remote_code=True)
```

注意：在使用 `bi_so101_fold_cloth` 时，请在检索环境后立即调用 `initialize()`，然后再执行任何其他操作。

点击展开代码示例

```
import torch
from lerobot.envs.factory import make_env

# Load from the hub
envs_dict = make_env("LightwheelAI/leisaac_env:envs/bi_so101_fold_cloth.py", n_envs=1, trust_remote_code=True)

# Access the environment
suite_name = next(iter(envs_dict))
sync_vector_env = envs_dict[suite_name][0]
# retrieve the isaac environment from the sync vector env
env = sync_vector_env.envs[0].unwrapped

# NOTE: initialize() first
env.initialize()

# other operation with env...
```

  [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/envhub_leisaac.mdx)
# 来源

https://hugging-face.cn/docs/lerobot/hilserl_sim

# 在仿真中训练 RL

本指南解释了在使用 LeRobot 框架进行人机在环 (Human-In-the-Loop, HIL) 强化学习时，如何使用 `gym_hil` 仿真环境来替代真实机器人。

`gym_hil` 是一个提供了与 Gymnasium 兼容的仿真环境的软件包，专为人机在环强化学习而设计。这些环境允许您：

* 在仿真中训练策略，以便在真实机器人上训练之前测试 RL 技术栈
* 使用游戏手柄或键盘等外部设备在仿真中收集演示数据
* 在策略学习过程中进行人工干预

目前，主要环境是基于 MuJoCo 的 Franka Panda 机器人仿真，包含如抓取立方体等任务。

## 安装

首先，在 LeRobot 环境中安装 `gym_hil` 软件包

```
pip install -e ".[hilserl]"
```

## 我需要什么？

* 一个用于控制机器人的游戏手柄或键盘
* 一个 Nvidia GPU

## 配置

要在 LeRobot 中使用 `gym_hil`，您需要创建配置文件。这里提供了一个示例 [此处](https://hugging-face.cn/datasets/lerobot/config_examples/resolve/main/rl/gym_hil/env_config.json)。关键配置部分包括：

### 环境类型与任务

```
{
  "env": {
    "type": "gym_manipulator",
    "name": "gym_hil",
    "task": "PandaPickCubeGamepad-v0",
    "fps": 10
  },
  "device": "cuda"
}
```

可用任务

* `PandaPickCubeBase-v0`：基础环境
* `PandaPickCubeGamepad-v0`：支持游戏手柄控制
* `PandaPickCubeKeyboard-v0`：支持键盘控制

### 处理器配置

```
{
  "env": {
    "processor": {
      "control_mode": "gamepad",
      "gripper": {
        "use_gripper": true,
        "gripper_penalty": -0.02
      },
      "reset": {
        "control_time_s": 15.0,
        "fixed_reset_joint_positions": [
          0.0, 0.195, 0.0, -2.43, 0.0, 2.62, 0.785
        ]
      },
      "inverse_kinematics": {
        "end_effector_step_sizes": {
          "x": 0.025,
          "y": 0.025,
          "z": 0.025
        }
      }
    }
  }
}
```

重要参数

* `gripper.gripper_penalty`：夹持器过度移动的惩罚值
* `gripper.use_gripper`：是否启用夹持器控制
* `inverse_kinematics.end_effector_step_sizes`：末端执行器在 x,y,z 轴上的步长大小
* `control_mode`：设置为 `"gamepad"` 以使用游戏手柄控制器

## 使用 LeRobot 的 HIL RL 运行

### 基本用法

要运行环境，请将模式（mode）设置为 null

```
python -m lerobot.rl.gym_manipulator --config_path path/to/gym_hil_env.json
```

### 记录数据集

要收集数据集，请将模式设置为 `record`，同时定义 repo\_id 和要记录的剧集（episodes）数量

```
{
  "env": {
    "type": "gym_manipulator",
    "name": "gym_hil",
    "task": "PandaPickCubeGamepad-v0"
  },
  "dataset": {
    "repo_id": "username/sim_dataset",
    "root": null,
    "task": "pick_cube",
    "num_episodes_to_record": 10,
    "replay_episode": null,
    "push_to_hub": true
  },
  "mode": "record"
}
```

```
python -m lerobot.rl.gym_manipulator --config_path path/to/gym_hil_env.json
```

### 训练策略

要训练策略，请参考 [此处](https://hugging-face.cn/datasets/lerobot/config_examples/resolve/main/rl/gym_hil/train_config.json) 可用的配置示例，并运行 actor 和 learner 服务器

```
python -m lerobot.rl.actor --config_path path/to/train_gym_hil_env.json
```

在另一个终端中，运行 learner 服务器

```
python -m lerobot.rl.learner --config_path path/to/train_gym_hil_env.json
```

仿真环境提供了一种安全且可重复的方式，用于在部署到真实机器人之前开发和测试您的人机在环强化学习组件。

恭喜 🎉，您已完成本教程！

> 如果你有任何问题或需要帮助，请在 [Discord](https://discord.com/invite/s3KuuzsPFb) 上联系我们。

论文引用

```
@article{luo2024precise,
  title={Precise and Dexterous Robotic Manipulation via Human-in-the-Loop Reinforcement Learning},
  author={Luo, Jianlan and Xu, Charles and Wu, Jeffrey and Levine, Sergey},
  journal={arXiv preprint arXiv:2410.21845},
  year={2024}
}
```

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/hilserl_sim.mdx)
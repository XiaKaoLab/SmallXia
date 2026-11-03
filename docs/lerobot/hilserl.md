# 来源

https://hugging-face.cn/docs/lerobot/hilserl

# HIL-SERL 真实机器人训练工作流程指南

在本教程中，您将使用 LeRobot 完成完整的人机回环样本高效强化学习 (HIL-SERL) 工作流程。您只需几个小时即可掌握在真实机器人上通过强化学习训练策略的方法。

HIL-SERL 是一种样本高效的强化学习算法，它结合了人类演示、在线学习和人工干预。该方法从少量人类演示开始，利用它们训练一个奖励分类器，然后采用执行者-学习者架构，人类可以在策略执行过程中进行干预，以引导探索并纠正不安全的行为。在本教程中，您将使用游戏手柄进行干预，并在学习过程中控制机器人。

它结合了三个关键要素：

1. **离线演示与奖励分类器：** 少量的人类远程操作片段加上基于视觉的成功检测器，为策略提供了一个良好的初始起点。
2. **带有人工干预的机器人端执行者/学习者循环：** 分布式软执行者-评论家 (SAC) 学习者在物理机器人上更新策略，同时执行者进行探索；人类可以随时介入以纠正危险或无效的行为。
3. **安全与效率工具：** 关节/末端执行器 (EE) 边界、感兴趣区域 (ROI) 裁剪预处理和 WandB 监控，确保数据有效且硬件安全。

这些要素共同作用，使 HIL-SERL 能够实现近乎完美的任务成功率，且比仅使用模仿学习的基线方法具有更快的周期时间。

![HIL-SERL workflow](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/hilserl-main-figure.png "HIL-SERL workflow")

*HIL-SERL 工作流程，Luo 等人，2024*

本指南提供了使用 LeRobot 的 HilSerl 实现方案在真实机器人上训练机器人策略的分步说明。

## 我需要什么？

* 一个游戏手柄（推荐）或键盘来控制机器人
* 一块 Nvidia GPU
* 一个带有跟随臂和主控臂的真实机器人（如果使用键盘或游戏手柄，则可选）
* 用于运动学包的机器人 URDF 文件（检查 `lerobot/model/kinematics.py`）

## 我可以训练什么样的任务？

可以使用 HIL-SERL 训练各种操作任务。一些建议：

* 从简单的任务开始，以了解系统是如何工作的。
  + 将立方体推向目标区域
  + 用夹爪拾取并提升立方体
* 避免极长的时间跨度任务。专注于可以在 5-10 秒内完成的任务。
* 一旦您对系统的工作方式有了很好的了解，就可以尝试更复杂的任务和更长的时间跨度。
  + 拾取并放置立方体
  + 使用双臂抓取物体的双臂任务
  + 将物体从一只手臂转移到另一只手臂的移交任务
  + 尽情发挥吧！

## 安装带有 HIL-SERL 的 LeRobot

要安装带有 HIL-SERL 的 LeRobot，您需要安装 `hilserl` 额外组件。

```
pip install -e ".[hilserl]"
```

## 真实机器人训练工作流程

### 理解配置

训练过程从 HILSerl 环境的正确配置开始。主要的配置类是 `lerobot/rl/gym_manipulator.py` 中的 `GymManipulatorConfig`，其中包含嵌套的 `HILSerlRobotEnvConfig` 和 `DatasetConfig`。配置被组织为集中的、嵌套的子配置。

```
class GymManipulatorConfig:
    env: HILSerlRobotEnvConfig    # Environment configuration (nested)
    dataset: DatasetConfig    # Dataset recording/replay configuration (nested)
    mode: str | None = None    # "record", "replay", or None (for training)
    device: str = "cpu"    # Compute device

class HILSerlRobotEnvConfig(EnvConfig):
    robot: RobotConfig | None = None    # Main robot agent (defined in `lerobot/robots`)
    teleop: TeleoperatorConfig | None = None    # Teleoperator agent, e.g., gamepad or leader arm
    processor: HILSerlProcessorConfig    # Processing pipeline configuration (nested)
    name: str = "real_robot"    # Environment name
    task: str | None = None    # Task identifier
    fps: int = 10    # Control frequency

# Nested processor configuration
class HILSerlProcessorConfig:
    control_mode: str = "gamepad"    # Control mode
    observation: ObservationConfig | None = None    # Observation processing settings
    image_preprocessing: ImagePreprocessingConfig | None = None    # Image crop/resize settings
    gripper: GripperConfig | None = None    # Gripper control and penalty settings
    reset: ResetConfig | None = None    # Environment reset and timing settings
    inverse_kinematics: InverseKinematicsConfig | None = None    # IK processing settings
    reward_classifier: RewardClassifierConfig | None = None    # Reward classifier settings
    max_gripper_pos: float | None = 100.0    # Maximum gripper position

# Sub-configuration classes
class ObservationConfig:
    add_joint_velocity_to_observation: bool = False    # Add joint velocities to state
    add_current_to_observation: bool = False    # Add motor currents to state
    display_cameras: bool = False    # Display camera feeds during execution

class ImagePreprocessingConfig:
    crop_params_dict: dict[str, tuple[int, int, int, int]] | None = None    # Image cropping parameters
    resize_size: tuple[int, int] | None = None    # Target image size

class GripperConfig:
    use_gripper: bool = True    # Enable gripper control
    gripper_penalty: float = 0.0    # Penalty for inappropriate gripper usage

class ResetConfig:
    fixed_reset_joint_positions: Any | None = None    # Joint positions for reset
    reset_time_s: float = 5.0    # Time to wait during reset
    control_time_s: float = 20.0    # Maximum episode duration
    terminate_on_success: bool = True    # Whether to terminate episodes on success detection

class InverseKinematicsConfig:
    urdf_path: str | None = None    # Path to robot URDF file
    target_frame_name: str | None = None    # End-effector frame name
    end_effector_bounds: dict[str, list[float]] | None = None    # EE workspace bounds
    end_effector_step_sizes: dict[str, float] | None = None    # EE step sizes per axis

class RewardClassifierConfig:
    pretrained_path: str | None = None    # Path to pretrained reward classifier
    success_threshold: float = 0.5    # Success detection threshold
    success_reward: float = 1.0    # Reward value for successful episodes

# Dataset configuration
class DatasetConfig:
    repo_id: str    # LeRobot dataset repository ID
    task: str    # Task identifier
    root: str | None = None    # Local dataset root directory
    num_episodes_to_record: int = 5    # Number of episodes for recording
    replay_episode: int | None = None    # Episode index for replay
    push_to_hub: bool = False    # Whether to push datasets to Hub
```

### 处理器流水线架构

HIL-SERL 使用模块化的处理器流水线架构，通过一系列可组合的步骤来处理机器人的观测数据和动作。该流水线分为两个主要部分：

#### 环境处理器流水线

环境处理器 (`env_processor`) 处理传入的观测数据和环境状态：

1. **VanillaObservationProcessorStep**：将原始机器人观测数据转换为标准化格式
2. **JointVelocityProcessorStep**（可选）：将关节速度信息添加到观测数据中
3. **MotorCurrentProcessorStep**（可选）：将电机电流读数添加到观测数据中
4. **ForwardKinematicsJointsToEE**（可选）：从关节位置计算末端执行器姿态
5. **ImageCropResizeProcessorStep**（可选）：裁剪并调整相机图像大小
6. **TimeLimitProcessorStep**（可选）：强制执行片段时长限制
7. **GripperPenaltyProcessorStep**（可选）：对不当使用夹爪的行为施加惩罚
8. **RewardClassifierProcessorStep**（可选）：使用视觉模型的自动奖励检测
9. **AddBatchDimensionProcessorStep**：将数据转换为用于神经网络处理的批处理格式
10. **DeviceProcessorStep**：将数据移动到指定的计算设备（CPU/GPU）

#### 动作处理器流水线

动作处理器 (`action_processor`) 处理传出的动作和人工干预：

1. **AddTeleopActionAsComplimentaryDataStep**：捕获远程操作员的动作以供记录
2. **AddTeleopEventsAsInfoStep**：记录干预事件和片段控制信号
3. **InterventionActionProcessorStep**：处理人工干预和片段终止
4. **逆运动学流水线**（启用时）
   * **MapDeltaActionToRobotActionStep**：将增量动作转换为机器人动作格式
   * **EEReferenceAndDelta**：计算末端执行器参考和增量位移
   * **EEBoundsAndSafety**：强制执行工作空间安全边界
   * **InverseKinematicsEEToJoints**：将末端执行器动作转换为关节目标
   * **GripperVelocityToJoint**：处理夹爪控制命令

#### 配置示例

**基础观测处理**:

```
{
  "env": {
    "processor": {
      "observation": {
        "add_joint_velocity_to_observation": true,
        "add_current_to_observation": false,
        "display_cameras": false
      }
    }
  }
}
```

**图像处理**:

```
{
  "env": {
    "processor": {
      "image_preprocessing": {
        "crop_params_dict": {
          "observation.images.front": [180, 250, 120, 150],
          "observation.images.side": [180, 207, 180, 200]
        },
        "resize_size": [128, 128]
      }
    }
  }
}
```

**逆运动学设置**:

```
{
  "env": {
    "processor": {
      "inverse_kinematics": {
        "urdf_path": "path/to/robot.urdf",
        "target_frame_name": "end_effector",
        "end_effector_bounds": {
          "min": [0.16, -0.08, 0.03],
          "max": [0.24, 0.2, 0.1]
        },
        "end_effector_step_sizes": {
          "x": 0.02,
          "y": 0.02,
          "z": 0.02
        }
      }
    }
  }
}
```

### 高级观测处理

HIL-SERL 框架支持额外的观测处理功能，可以提高策略学习的效果。

#### 关节速度处理

启用关节速度估计，为策略提供运动信息。

```
{
  "env": {
    "processor": {
      "observation": {
        "add_joint_velocity_to_observation": true
      }
    }
  }
}
```

此处理器：

* 使用连续关节位置读数之间的有限差分来估计关节速度
* 将速度信息添加到观测状态向量中
* 适用于需要动态任务运动感知的策略

#### 电机电流处理

监控电机电流以检测接触力和负载条件。

```
{
  "env": {
    "processor": {
      "observation": {
        "add_current_to_observation": true
      }
    }
  }
}
```

此处理器：

* 从机器人的控制系统读取电机电流值
* 将电流测量值添加到观测状态向量中
* 有助于检测接触事件、物体重量和机械阻力
* 适用于接触密集型操作任务

#### 组合观测处理

您可以同时启用多种观测处理功能。

```
{
  "env": {
    "processor": {
      "observation": {
        "add_joint_velocity_to_observation": true,
        "add_current_to_observation": true,
        "display_cameras": false
      }
    }
  }
}
```

**注意**：启用额外的观测功能会增加状态空间的维度，这可能需要调整您的策略网络架构，并可能需要收集更多的训练数据。

### 确定机器人工作空间边界

在收集演示之前，您需要确定机器人的合适操作边界。

这有助于通过以下两种方式简化在真实机器人上进行学习的问题：1) 通过将机器人的操作空间限制在解决任务所需的特定区域，从而避免不必要或不安全的探索；2) 允许在末端执行器空间而不是关节空间进行训练。从经验来看，强化学习操作任务时，在关节空间学习通常是一个更难的问题——有些任务在关节空间中几乎不可能学会，但当动作空间转换为末端执行器坐标时就变得可行了。

**使用 lerobot-find-joint-limits**

此脚本可帮助您找到机器人末端执行器的安全操作边界。鉴于您有跟随臂和主控臂，您可以使用该脚本找到训练期间应用于跟随臂的边界。限制动作空间将减少代理的冗余探索并确保安全。

```
lerobot-find-joint-limits \
  --robot.type=so100_follower \
  --robot.port=/dev/tty.usbmodem58760431541 \
  --robot.id=black \
  --teleop.type=so100_leader \
  --teleop.port=/dev/tty.usbmodem58760431551 \
  --teleop.id=blue
```

**工作流程**

1. 运行脚本并在解决任务的空间内移动机器人。
2. 脚本将记录末端执行器的最小和最大位置以及关节角度，并将它们打印到控制台，例如：

   ```
   Max ee position [0.2417 0.2012 0.1027]
   Min ee position [0.1663 -0.0823 0.0336]
   Max joint positions [-20.0, -20.0, -20.0, -20.0, -20.0, -20.0]
   Min joint positions [50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
   ```
3. 在您的远程操作设备配置 (TeleoperatorConfig) 的 `end_effector_bounds` 字段中使用这些值。

**配置示例**

```
"end_effector_bounds": {
    "max": [0.24, 0.20, 0.10],
    "min": [0.16, -0.08, 0.03]
}
```

### 收集演示

定义好边界后，您可以安全地收集训练演示。使用离策略算法进行强化学习，使我们能够使用收集到的离线数据集来提高学习过程的效率。

**设置记录模式**

创建一个用于记录演示的配置文件（或编辑现有文件，如 [env\_config.json](https://hugging-face.cn/datasets/lerobot/config_examples/resolve/main/rl/env_config.json)）

1. 将根级别的 `mode` 设置为 `"record"`
2. 在 `dataset` 部分为您的数据集指定唯一的 `repo_id`（例如，“用户名/任务名称”）
3. 在 `dataset` 部分将 `num_episodes_to_record` 设置为您要收集的演示数量
4. 最初将 `env.processor.image_preprocessing.crop_params_dict` 设置为 `{}`（我们稍后会确定裁剪区域）
5. 在 `env` 部分配置 `env.robot`、`env.teleop` 和其他硬件设置

配置示例部分

```
{
  "env": {
    "type": "gym_manipulator",
    "name": "real_robot",
    "fps": 10,
    "processor": {
      "control_mode": "gamepad",
      "observation": {
        "display_cameras": false
      },
      "image_preprocessing": {
        "crop_params_dict": {},
        "resize_size": [128, 128]
      },
      "gripper": {
        "use_gripper": true,
        "gripper_penalty": 0.0
      },
      "reset": {
        "reset_time_s": 5.0,
        "control_time_s": 20.0
      }
    },
    "robot": {
      // ... robot configuration ...
    },
    "teleop": {
      // ... teleoperator configuration ...
    }
  },
  "dataset": {
    "repo_id": "username/pick_lift_cube",
    "root": null,
    "task": "pick_and_lift",
    "num_episodes_to_record": 15,
    "replay_episode": 0,
    "push_to_hub": true
  },
  "mode": "record",
  "device": "cpu"
}
```

### 使用远程操作设备

除了机器人，您还需要一个远程操作设备来控制它，以便收集任务数据集并在在线训练期间执行干预。我们支持使用游戏手柄、键盘或机器人的主控臂。

HIL-Serl 在机器人的末端执行器空间学习动作。因此，远程操作将控制末端执行器的 x、y、z 位移。

为此，我们需要定义一个在末端执行器空间采取动作的机器人版本。查看机器人类 `SO100FollowerEndEffector` 及其配置 `SO100FollowerEndEffectorConfig`，了解与末端执行器空间相关的默认参数。

```
class SO100FollowerEndEffectorConfig(SO100FollowerConfig):
    """Configuration for the SO100FollowerEndEffector robot."""

    # Default bounds for the end-effector position (in meters)
    end_effector_bounds: dict[str, list[float]] = field( # bounds for the end-effector in x,y,z direction
        default_factory=lambda: {
            "min": [-1.0, -1.0, -1.0],  # min x, y, z
            "max": [1.0, 1.0, 1.0],  # max x, y, z
        }
    )

    max_gripper_pos: float = 50 # maximum gripper position that the gripper will be open at

    end_effector_step_sizes: dict[str, float] = field( # maximum step size for the end-effector in x,y,z direction
        default_factory=lambda: {
            "x": 0.02,
            "y": 0.02,
            "z": 0.02,
        }
    )
```

`Teleoperator` 定义了远程操作设备。您可以查看 `lerobot/teleoperators` 中可用远程操作设备的列表。

**设置游戏手柄**

游戏手柄提供了一种非常方便的控制机器人和片段状态的方式。

要设置游戏手柄，您需要将 `control_mode` 设置为 `"gamepad"` 并在配置文件中定义 `teleop` 部分。

```
{
  "env": {
    "teleop": {
      "type": "gamepad",
      "use_gripper": true
    },
    "processor": {
      "control_mode": "gamepad",
      "gripper": {
        "use_gripper": true
      }
    }
  }
}
```

![Figure shows the control mappings on a Logitech gamepad.](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/gamepad_guide.jpg?raw=true "Gamepad Control Mapping")

*用于机器人控制和片段管理的按钮映射*

**设置 SO101 主控臂**

SO101 主控臂具有减速齿轮，使其能够在探索过程中移动并跟踪跟随臂。因此，接管操作比无齿轮的 SO100 更平滑。

要设置 SO101 主控臂，您需要将 `control_mode` 设置为 `"leader"` 并在配置文件中定义 `teleop` 部分。

```
{
  "env": {
    "teleop": {
      "type": "so101_leader",
      "port": "/dev/tty.usbmodem585A0077921",
      "use_degrees": true
    },
    "processor": {
      "control_mode": "leader",
      "gripper": {
        "use_gripper": true
      }
    }
  }
}
```

为了标注片段的成功/失败，**您将需要**使用键盘，按 `s` 表示成功，按 `esc` 表示失败。在在线训练期间，按 `space` 接管策略，再次按 `space` 将控制权交还给策略。

**视频：SO101 主控臂远程操作**

[](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/so101_leader_tutorial.mp4)

*SO101 主控臂远程操作示例，主控臂跟踪跟随臂，按 `space` 进行干预*

**记录演示**

开始记录过程，可以在 [此处](https://hugging-face.cn/datasets/aractingi/lerobot-example-config-files/blob/main/env_config_so100.json) 找到配置文件的示例

```
python -m lerobot.rl.gym_manipulator --config_path src/lerobot/configs/env_config_so100.json
```

记录期间

1. 机器人将重置为配置文件 `env.processor.reset.fixed_reset_joint_positions` 中定义的初始位置
2. 成功完成任务
3. 当您按下“成功”按钮时，片段以奖励 1 结束
4. 如果达到时间限制，或者按下失败按钮，片段以奖励 0 结束
5. 您可以通过按“重新记录”按钮来重新记录片段
6. 该过程会自动继续到下一个片段
7. 记录完所有片段后，数据集将被推送到 Hugging Face Hub（可选）并保存在本地

### 处理数据集

收集演示后，处理它们以确定最佳相机裁剪区域。强化学习对背景干扰很敏感，因此将图像裁剪到相关工作空间区域非常重要。

视觉强化学习算法直接从像素输入中学习，这使得它们容易受到无关视觉信息的影响。背景元素（如光线变化、阴影、人员移动或工作空间外的物体）会干扰学习过程。良好的 ROI 选择应该：

* 仅包含任务发生的基本工作空间
* 捕获机器人的末端执行器和任务涉及的所有物体
* 排除不必要的背景元素和干扰

注意：如果您已经知道裁剪参数，可以跳过此步骤，只需在记录期间设置配置文件中的 `crop_params_dict` 即可。

**确定裁剪参数**

使用 `crop_dataset_roi.py` 脚本以交互方式选择相机图像中的感兴趣区域

```
python -m lerobot.rl.crop_dataset_roi --repo-id username/pick_lift_cube
```

1. 对于每个相机视角，脚本将显示第一帧
2. 在相关工作空间区域周围绘制一个矩形
3. 按“c”确认选择
4. 对所有相机视角重复此操作
5. 脚本输出裁剪参数并创建一个新的已裁剪数据集

示例输出

```
Selected Rectangular Regions of Interest (top, left, height, width):
observation.images.side: [180, 207, 180, 200]
observation.images.front: [180, 250, 120, 150]
```

![](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/crop_dataset.gif)

*用于选择感兴趣区域的交互式裁剪工具*

**更新配置**

将这些裁剪参数添加到您的训练配置中

```
{
  "env": {
    "processor": {
      "image_preprocessing": {
        "crop_params_dict": {
          "observation.images.side": [180, 207, 180, 200],
          "observation.images.front": [180, 250, 120, 150]
        },
        "resize_size": [128, 128]
      }
    }
  }
}
```

**推荐的图像分辨率**

大多数基于视觉的策略已在 **128×128**（默认）或 **64×64** 像素的正方形输入上进行了验证。因此，我们建议将 resize\_size 参数设置为 [128, 128] —— 如果您需要节省 GPU 内存和带宽，则设置为 [64, 64]。其他分辨率也是可行的，但尚未经过广泛测试。

### 训练奖励分类器

奖励分类器在 HIL-SERL 工作流程中发挥重要作用，通过自动化奖励分配和自动检测片段成功来提高效率。奖励分类器无需手动定义奖励函数或依赖每一步的人工反馈，而是学习从视觉观测中预测成功/失败。这使强化学习算法能够通过根据机器人的相机输入提供一致且自动化的奖励信号来高效学习。

本指南介绍了如何为 LeRobot 的人机回环强化学习实现方案训练奖励分类器。奖励分类器学习预测给定状态下的奖励值，该值可用于强化学习设置中以训练策略。

**注意**：训练奖励分类器是可选的。您可以先通过使用游戏手柄或键盘手动标注成功来开始第一轮强化学习实验。

`modeling_classifier.py` 中的奖励分类器实现使用预训练的视觉模型来处理图像。它可以为二进制奖励输出单个值以预测成功/失败案例，或为多分类设置输出多个值。

**为奖励分类器收集数据集**

在训练之前，您需要收集一个带有标注示例的数据集。`gym_manipulator.py` 中的 `record_dataset` 函数支持收集观测、动作和奖励数据集的过程。

要收集数据集，您需要根据 HILSerlRobotEnvConfig 修改环境配置中的一些参数。

```
python -m lerobot.rl.gym_manipulator --config_path src/lerobot/configs/reward_classifier_train_config.json
```

**数据收集的关键参数**

* **mode**：设置为 `"record"` 以收集数据集（在根级别）
* **dataset.repo\_id**：`"hf_username/dataset_name"`，数据集名称和 Hub 上的存储库
* **dataset.num\_episodes\_to\_record**：要记录的片段数量
* **env.processor.reset.terminate\_on\_success**：当检测到成功时是否自动终止片段（默认：`true`）
* **env.fps**：记录的每秒帧数
* **dataset.push\_to\_hub**：是否将数据集推送到 Hub

`env.processor.reset.terminate_on_success` 参数允许您控制片段终止行为。当设置为 `false` 时，即使检测到成功，片段也将继续，从而允许您使用奖励=1 的标签收集更多的正样本。这对于训练奖励分类器至关重要，因为它在数据集中提供了更多的成功状态示例。当设置为 `true`（默认）时，片段在检测到成功时立即终止。

**重要**：对于奖励分类器训练，将 `terminate_on_success` 设置为 `false` 以收集足够的正样本。对于常规的 HIL-SERL 训练，保持为 `true` 以便在任务成功完成后自动终止片段。

数据收集的配置示例部分

```
{
  "env": {
    "type": "gym_manipulator",
    "name": "real_robot",
    "fps": 10,
    "processor": {
      "reset": {
        "reset_time_s": 5.0,
        "control_time_s": 20.0,
        "terminate_on_success": false
      },
      "gripper": {
        "use_gripper": true
      }
    },
    "robot": {
      // ... robot configuration ...
    },
    "teleop": {
      // ... teleoperator configuration ...
    }
  },
  "dataset": {
    "repo_id": "hf_username/dataset_name",
    "dataset_root": "data/your_dataset",
    "task": "reward_classifier_task",
    "num_episodes_to_record": 20,
    "replay_episode": null,
    "push_to_hub": true
  },
  "mode": "record",
  "device": "cpu"
}
```

**奖励分类器配置**

奖励分类器使用 `configuration_classifier.py` 进行配置。以下是关键参数：

* **model\_name**：基础模型架构（例如，我们主要使用 `"helper2424/resnet10"`）
* **model\_type**: `"cnn"` 或 `"transformer"`
* **num\_cameras**: 摄像头输入的数量
* **num\_classes**: 输出类别的数量（对于二分类成功/失败，通常为 2）
* **hidden\_dim**: 隐藏表示的维度
* **dropout\_rate**: 正则化参数
* **learning\_rate**: 优化器的学习率

训练 [奖励分类器](https://hugging-face.cn/datasets/aractingi/lerobot-example-config-files/blob/main/reward_classifier_train_config.json) 的配置示例

```
{
  "policy": {
    "type": "reward_classifier",
    "model_name": "helper2424/resnet10",
    "model_type": "cnn",
    "num_cameras": 2,
    "num_classes": 2,
    "hidden_dim": 256,
    "dropout_rate": 0.1,
    "learning_rate": 1e-4,
    "device": "cuda",
    "use_amp": true,
    "input_features": {
      "observation.images.front": {
        "type": "VISUAL",
        "shape": [3, 128, 128]
      },
      "observation.images.side": {
        "type": "VISUAL",
        "shape": [3, 128, 128]
      }
    }
  }
}
```

**训练分类器**

要训练分类器，请使用 `train.py` 脚本并传入您的配置

```
lerobot-train --config_path path/to/reward_classifier_train_config.json
```

**部署和测试模型**

要使用您训练好的奖励分类器，请配置 `HILSerlRobotEnvConfig` 以使用您的模型

```
config = GymManipulatorConfig(
    env=HILSerlRobotEnvConfig(
        processor=HILSerlProcessorConfig(
            reward_classifier=RewardClassifierConfig(
                pretrained_path="path_to_your_pretrained_trained_model"
            )
        ),
        # Other environment parameters
    ),
    dataset=DatasetConfig(...),
    mode=None  # For training
)
```

或在 json 配置文件中设置该参数。

```
{
  "env": {
    "processor": {
      "reward_classifier": {
        "pretrained_path": "path_to_your_pretrained_model",
        "success_threshold": 0.7,
        "success_reward": 1.0
      },
      "reset": {
        "terminate_on_success": true
      }
    }
  }
}
```

运行 `gym_manipulator.py` 来测试模型。

```
python -m lerobot.rl.gym_manipulator --config_path path/to/env_config.json
```

奖励分类器将根据机器人摄像头获取的视觉输入自动提供奖励。

**训练奖励分类器的工作流程示例**

1. **创建配置文件**：为奖励分类器和环境创建必要的 json 配置文件。请查看[此处](https://hugging-face.cn/datasets/lerobot/config_examples/resolve/main/reward_classifier/config.json)的示例。
2. **收集数据集**:

   ```
   python -m lerobot.rl.gym_manipulator --config_path src/lerobot/configs/env_config.json
   ```
3. **训练分类器**:

   ```
   lerobot-train --config_path src/lerobot/configs/reward_classifier_train_config.json
   ```
4. **测试分类器**:

   ```
   python -m lerobot.rl.gym_manipulator --config_path src/lerobot/configs/env_config.json
   ```

### 使用 Actor-Learner（执行者-学习者）进行训练

LeRobot 系统采用分布式执行者-学习者（actor-learner）架构进行训练。这种架构将机器人交互与学习过程解耦，使它们能够并行运行而互不阻塞。执行者（actor）服务器负责处理机器人的观测和动作，并将交互数据发送给学习者（learner）服务器。学习者服务器执行梯度下降并定期更新执行者的策略权重。您需要启动两个进程：一个学习者和一个执行者。

**配置设置**

创建训练配置文件（示例见[此处](https://hugging-face.cn/datasets/lerobot/config_examples/resolve/main/rl/train_config.json)）。训练配置基于 `lerobot/configs/train.py` 中的主 `TrainRLServerPipelineConfig` 类。

1. 配置策略设置（`type="sac"`, `device` 等）
2. 将 `dataset` 设置为您裁剪后的数据集
3. 使用裁剪参数配置环境设置
4. 检查 [configuration\_sac.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/sac/configuration_sac.py#L79) 中与 SAC 相关的其他参数。
5. 验证 `policy` 配置是否正确，且具备适用于您任务的正确 `input_features` 和 `output_features`。

**启动学习者**

首先，启动学习者服务器进程

```
python -m lerobot.rl.learner --config_path src/lerobot/configs/train_config_hilserl_so100.json
```

学习者：

* 初始化策略网络
* 准备重放缓冲区（replay buffers）
* 开启 `gRPC` 服务器以与执行者通信
* 处理转换数据并更新策略

**启动执行者**

在另一个终端中，使用相同的配置启动执行者进程

```
python -m lerobot.rl.actor --config_path src/lerobot/configs/train_config_hilserl_so100.json
```

执行者：

* 通过 `gRPC` 连接到学习者
* 初始化环境
* 执行策略展开（rollouts）以收集经验
* 将转换数据发送给学习者
* 接收更新后的策略参数

**训练流程**

训练过程自动进行

1. 执行者在环境中执行策略
2. 收集并向学习者发送转换数据
3. 学习者根据这些转换数据更新策略
4. 更新后的策略参数传回执行者
5. 该过程将持续进行，直到达到指定的步骤限制

**人在回路（Human in the Loop）**

* 高效学习的关键在于通过人工干预提供修正反馈，并完成任务以辅助策略学习和探索。
* 若要进行人工干预，您可以按下游戏手柄右上方的扳机键（或键盘上的 `空格键`）。这将暂停策略动作并允许您接管控制。
* 一个成功的实验是：人类在开始时需要频繁干预，但随着策略的改进，干预次数会逐渐减少。您可以在 `wandb` 仪表板中监控干预率。

![Figure shows the control mappings on a Logitech gamepad.](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/hil_effect.png?raw=true "Gamepad Control Mapping")

*示例：展示人工干预如何随时间推移帮助引导策略学习*

* 该图显示了每交互步骤的片段奖励图。图中展示了人工干预对策略学习的影响。
* 橙色曲线为没有任何人工干预的实验，粉色和蓝色曲线为有人工干预的实验。
* 我们可以观察到，在存在人工干预的情况下，策略开始达到最高奖励所需的步数减少了四分之一。

**监控与调试**

如果您在配置中将 `wandb.enable` 设置为 `true`，则可以通过 [Weights & Biases](https://wandb.ai/site/) 仪表板实时监控训练进度。

### 人工干预指南

学习过程对干预策略非常敏感。这需要经过几次运行才能理解如何有效干预。一些提示和建议：

* 在训练开始时，让策略进行几次探索。
* 避免长时间干预。尝试在机器人偏离轨道时进行干预以纠正其行为。
* 一旦策略开始执行任务（即使不完美），您可以将干预限制为简单的快速动作，例如简单的抓取指令。

理想的行为是您的干预率应在训练过程中逐渐下降，如下图所示。

![Intervention rate](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/intervention_rate_tutorial_rl.png?raw=true "Intervention rate during training")

*拾取立方体任务训练期间的干预率曲线图*

### 关键超参数调整

某些配置值对训练稳定性和速度有显著影响：

* **`temperature_init`** (`policy.temperature_init`) – SAC 中的初始熵温度。较高的值鼓励更多探索；较低的值使策略在早期更趋于确定性。一个好的起点是 `1e-2`。我们观察到设置过高会使人工干预失效并减慢学习速度。
* **`policy_parameters_push_frequency`** (`policy.actor_learner_config.policy_parameters_push_frequency`) – 学习者向执行者推送权重的间隔（单位：*秒*）。默认值为 `4 s`。减少到 **1-2 s** 可以提供更新鲜的权重（代价是增加网络流量）；仅在您的网络连接速度慢时增加该值，因为这会降低采样效率。
* **`storage_device`** (`policy.storage_device`) – 学习者保存策略参数的设备。如果您有空闲的 GPU 内存，请将其设置为 `"cuda"`（而不是默认的 `"cpu"`）。将权重保留在 GPU 上可消除 CPU→GPU 的传输开销，并显著提高每秒学习者的更新次数。

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

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/hilserl.mdx)
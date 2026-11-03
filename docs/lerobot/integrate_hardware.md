# 来源

https://hugging-face.cn/docs/lerobot/integrate_hardware

# 自带硬件

本教程将解释如何将您自己的机器人设计集成到 LeRobot 生态系统中，并使其能够访问我们的所有工具（数据收集、控制管线、策略训练和推理）。

为此，我们在 LeRobot 中提供了 [`Robot`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/robots/robot.py) 基类，它为实体机器人集成指定了标准接口。让我们来看看如何实现它。

## 先决条件

* 您自己的机器人，它公开了一个通信接口（例如：串口、CAN、TCP）
* 一种通过编程方式读取传感器数据并发送电机命令的方法，例如：制造商的 SDK 或 API，或您自己的协议实现。
* 您的环境中已安装 LeRobot。请参考我们的[安装指南](installation.md)。

## 选择您的电机

如果您使用的是飞特（Feetech）或 Dynamixel 电机，LeRobot 提供了内置的总线接口

* [`FeetechMotorsBus`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/feetech.py) – 用于控制飞特舵机
* [`DynamixelMotorsBus`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/dynamixel/dynamixel.py) – 用于控制 Dynamixel 舵机

请参考 [`MotorsBus`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/motors_bus.py) 抽象类以了解其 API。关于如何使用它的一个很好的示例，您可以查看我们自己的 [SO101 从机实现](https://github.com/huggingface/lerobot/blob/main/src/lerobot/robots/so_follower/so101_follower/so101_follower.py)

如果兼容，请使用这些接口。否则，您需要寻找或编写一个 Python 接口（本教程不涵盖此内容）

* 寻找现有的 Python SDK（或使用 C/C++ 绑定）
* 或者实现一个基础的通信封装（例如，通过 pyserial、socket 或 CANopen）

您并不孤单——社区的许多贡献都使用了自定义板卡或固件！

对于飞特和 Dynamixel，我们目前支持这些舵机： - 飞特： - STS & SMS 系列（协议 0）：`sts3215`、`sts3250`、`sm8512bl` - SCS 系列（协议 1）：`scs0009` - Dynamixel（仅协议 2.0）：`xl330-m077`、`xl330-m288`、`xl430-w250`、`xm430-w350`、`xm540-w270`、`xc430-w150`

如果您使用的飞特或 Dynamixel 舵机不在本列表中，您可以在 [飞特型号表](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/tables.py) 或 [Dynamixel 型号表](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/dynamixel/tables.py) 中添加它们。根据具体型号，这可能需要您添加特定于模型的信息。不过在大多数情况下，不需要做太多添加。

在接下来的章节中，我们将在示例中使用 `FeetechMotorsBus` 作为电机接口。如有必要，请将其替换并适配到您的电机。

## 步骤 1：子类化 Robot 接口

您首先需要为您的机器人指定配置类和一个字符串标识符（`name`）。如果您的机器人有您希望能够轻松更改的特殊需求，应该写在这里（例如：端口/地址、波特率）。

在这里，我们将默认为我们的机器人添加端口名称和一台相机

```
from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig
from lerobot.cameras.opencv import OpenCVCameraConfig
from lerobot.robots import RobotConfig


@RobotConfig.register_subclass("my_cool_robot")
@dataclass
class MyCoolRobotConfig(RobotConfig):
    port: str
    cameras: dict[str, CameraConfig] = field(
        default_factory={
            "cam_1": OpenCVCameraConfig(
                index_or_path=2,
                fps=30,
                width=480,
                height=640,
            ),
        }
    )
```

[相机教程](cameras.md)，以了解如何检测并添加您的相机。

接下来，我们将创建继承自 `Robot` 的实际机器人类。这个抽象类定义了一个协议，您必须遵守该协议，您的机器人才能与 LeRobot 的其他工具一起使用。

在这里，我们将创建一个带有一台相机的简单 5 自由度机器人。它可以是一个简单的机械臂，但请注意，`Robot` 抽象类并不对您机器人的外形规格做任何假设。在设计新机器人时，您可以尽情发挥您的想象力！

```
from lerobot.cameras import make_cameras_from_configs
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.robots import Robot

class MyCoolRobot(Robot):
    config_class = MyCoolRobotConfig
    name = "my_cool_robot"

    def __init__(self, config: MyCoolRobotConfig):
        super().__init__(config)
        self.bus = FeetechMotorsBus(
            port=self.config.port,
            motors={
                "joint_1": Motor(1, "sts3250", MotorNormMode.RANGE_M100_100),
                "joint_2": Motor(2, "sts3215", MotorNormMode.RANGE_M100_100),
                "joint_3": Motor(3, "sts3215", MotorNormMode.RANGE_M100_100),
                "joint_4": Motor(4, "sts3215", MotorNormMode.RANGE_M100_100),
                "joint_5": Motor(5, "sts3215", MotorNormMode.RANGE_M100_100),
            },
            calibration=self.calibration,
        )
        self.cameras = make_cameras_from_configs(config.cameras)
```

## 步骤 2：定义观察与动作特征

这两个属性定义了您的机器人与使用它的工具（例如数据收集或学习管线）之间的*接口协议*。

> 请注意，即使机器人尚未连接，这些属性也必须是可调用的，因此请避免依赖运行时硬件状态来定义它们。

### observation\_features

此属性应返回一个描述机器人传感器输出结构的字典。键与 `get_observation()` 返回的内容相匹配，值则描述了形状（对于数组/图像）或类型（对于简单数值）。

我们带有一台相机的 5 自由度机械臂的示例

```
@property
def _motors_ft(self) -> dict[str, type]:
    return {
        "joint_1.pos": float,
        "joint_2.pos": float,
        "joint_3.pos": float,
        "joint_4.pos": float,
        "joint_5.pos": float,
    }

@property
def _cameras_ft(self) -> dict[str, tuple]:
    return {
        cam: (self.cameras[cam].height, self.cameras[cam].width, 3) for cam in self.cameras
    }

@property
def observation_features(self) -> dict:
    return {**self._motors_ft, **self._cameras_ft}
```

在这种情况下，观察结果由一个存储每个电机位置和相机图像的简单字典组成。

### action\_features

此属性描述了您的机器人期望通过 `send_action()` 接收的命令。同样，键必须与期望的输入格式相匹配，值定义了每个命令的形状/类型。

在这里，我们只需使用与 `observation_features` 相同的关节本体感受特征（`self._motors_ft`）：发送的动作将仅是每个电机的目标位置。

```
def action_features(self) -> dict:
    return self._motors_ft
```

## 步骤 3：处理连接与断开连接

这些方法应该处理与硬件（例如串口、CAN 接口、USB 设备、相机）的通信开启和关闭。

### is\_connected

此属性应仅反映与机器人硬件的通信已建立。当此属性为 `True` 时，应能够使用 `get_observation()` 和 `send_action()` 对硬件进行读写。

```
@property
def is_connected(self) -> bool:
    return self.bus.is_connected and all(cam.is_connected for cam in self.cameras.values())
```

### connect()

此方法应当建立与硬件的通信。此外，如果您的机器人需要校准且尚未校准，默认情况下它应该启动校准程序。如果您的机器人需要某些特定的配置，也应该在这里调用。

```
def connect(self, calibrate: bool = True) -> None:
    self.bus.connect()
    if not self.is_calibrated and calibrate:
        self.calibrate()

    for cam in self.cameras.values():
        cam.connect()

    self.configure()
```

### disconnect()

此方法应该优雅地终止与硬件的通信：释放任何相关的资源（线程或进程）、关闭端口等。

在这里，我们已经在 `MotorsBus` 和 `Camera` 类中处理了这一点，所以我们只需要调用它们各自的 `disconnect()` 方法即可。

```
def disconnect(self) -> None:
    self.bus.disconnect()
    for cam in self.cameras.values():
        cam.disconnect()
```

## 步骤 4：支持校准与配置

LeRobot 支持自动保存和加载校准数据。这对于关节偏移量、零位或传感器对齐非常有用。

> 请注意，具体取决于您的硬件，这可能不适用。如果是这种情况，您只需将这些方法留空（即空操作 no-ops）即可。

```
@property
def is_calibrated(self) -> bool:
    return True

def calibrate(self) -> None:
    pass
```

### is\_calibrated

这应该反映您的机器人是否已加载所需的校准。

```
@property
def is_calibrated(self) -> bool:
    return self.bus.is_calibrated
```

### calibrate()

校准的目标有两个方面

* 了解每个电机的物理运动范围，以便仅在此范围内发送命令。
* 将原始电机位置归一化为合理的连续值（例如百分比、度数），而不是依赖于所用特定电机且无法在其他地方复制的任意离散值。

它应该实现校准的逻辑（如果相关）并更新 `self.calibration` 字典。如果您使用的是飞特或 Dynamixel 电机，我们的总线接口已经包含了可以提供帮助的方法。

```
def calibrate(self) -> None:
    self.bus.disable_torque()
    for motor in self.bus.motors:
        self.bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)

    input(f"Move {self} to the middle of its range of motion and press ENTER....")
    homing_offsets = self.bus.set_half_turn_homings()

    print(
        "Move all joints sequentially through their entire ranges "
        "of motion.\nRecording positions. Press ENTER to stop..."
    )
    range_mins, range_maxes = self.bus.record_ranges_of_motion()

    self.calibration = {}
    for motor, m in self.bus.motors.items():
        self.calibration[motor] = MotorCalibration(
            id=m.id,
            drive_mode=0,
            homing_offset=homing_offsets[motor],
            range_min=range_mins[motor],
            range_max=range_maxes[motor],
        )

    self.bus.write_calibration(self.calibration)
    self._save_calibration()
    print("Calibration saved to", self.calibration_fpath)
```

### configure()

使用此方法设置硬件的任何配置（舵机控制模式、控制器增益等）。这通常应该在连接时运行，并且应该是幂等的。

```
def configure(self) -> None:
    with self.bus.torque_disabled():
        self.bus.configure_motors()
        for motor in self.bus.motors:
            self.bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)
            self.bus.write("P_Coefficient", motor, 16)
            self.bus.write("I_Coefficient", motor, 0)
            self.bus.write("D_Coefficient", motor, 32)
```

## 步骤 5：实现传感器读取与动作发送

这些是最重要的运行时函数：核心 I/O 循环。

### get\_observation()

返回来自机器人的传感器值的字典。这些通常包括电机状态、相机帧、各种传感器等。在 LeRobot 框架中，这些观察结果将被送入策略中，以预测要采取的动作。字典的键和结构必须与 `observation_features` 匹配。

```
def get_observation(self) -> dict[str, Any]:
    if not self.is_connected:
        raise ConnectionError(f"{self} is not connected.")

    # Read arm position
    obs_dict = self.bus.sync_read("Present_Position")
    obs_dict = {f"{motor}.pos": val for motor, val in obs_dict.items()}

    # Capture images from cameras
    for cam_key, cam in self.cameras.items():
        obs_dict[cam_key] = cam.async_read()

    return obs_dict
```

### send\_action()

接受一个与 `action_features` 匹配的字典，并将其发送给您的硬件。您可以添加安全限制（裁剪、平滑）并返回实际发送的内容。

为了简单起见，我们在这里的示例中不会对动作进行任何修改。

```
def send_action(self, action: dict[str, Any]) -> dict[str, Any]:
    goal_pos = {key.removesuffix(".pos"): val for key, val in action.items()}

    # Send goal position to the arm
    self.bus.sync_write("Goal_Position", goal_pos)

    return action
```

## 添加遥操作器

为了实现遥操作设备，我们还提供了一个 [`Teleoperator`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/teleoperators/teleoperator.py) 基类。该类与 `Robot` 基类非常相似，同样不对外形规格做任何假设。

主要区别在于 I/O 函数：遥操作器允许您通过 `get_action` 产生动作，并可以通过 `send_feedback` 接收反馈动作。反馈可以是遥操作设备上任何可控的内容，这可以帮助操作人员理解所发送动作的后果。例如，主手臂（leader arm）上的运动/力反馈，或者游戏手柄上的振动。要实现遥操作器，您可以遵循本教程，并针对这两个方法进行适配。

## 使用您自己的 LeRobot 设备 🔌

通过创建一个独立的、可安装的 Python 包，您可以轻松地使用自己定制的硬件（无论是相机、机器人还是遥操作设备）来扩展 `lerobot`。如果您遵循一些简单的规范，`lerobot` 命令行工具（如 `lerobot-teleop` 和 `lerobot-record`）将**自动发现并集成您的创意成果**，而无需对 `lerobot` 源码进行任何修改。

本指南概述了您的插件必须遵循的规范。

### 4 项核心规范

为确保您的自定义设备可被发现，您必须遵守以下四条规则。

#### 1 . 创建具有特定前缀的可安装包

您的项目必须是一个标准的、可安装的 Python 包。至关重要的是，您的包名称（在 `pyproject.toml` 或 `setup.py` 中定义）必须以以下前缀之一开头

* 机器人使用 `lerobot_robot_`。
* 相机使用 `lerobot_camera_`。
* 遥操作设备使用 `lerobot_teleoperator_`。

这种前缀系统是 `lerobot` 在 Python 环境中自动找到您的插件的方式。

#### 2 . 遵循 SomethingConfig / Something 命名模式

您设备的实现类必须以其配置类命名，只需移除 `Config` 后缀即可。

* **配置类：** `MyAwesomeTeleopConfig`
* **设备类：** `MyAwesomeTeleop`

#### 3 . 将文件放在可预测的结构中

设备类（`MyAwesomeTeleop`）必须位于与其配置类（`MyAwesomeTeleopConfig`）相关的可预测模块中。`lerobot` 将自动在这些位置进行搜索

* 在与配置类**相同的模块**中。
* 在一个**以设备命名的子模块**中（例如，`my_awesome_teleop.py`）。

推荐且最简单的结构是，将它们放在同一目录下的、命名清晰的独立文件中。

#### 4 . 在 \_\_init\_\_.py 中公开类

您的包的 `__init__.py` 文件应该导入并公开配置类和设备类，使它们易于访问。

### 整合：一个完整示例

让我们创建一个名为 `my_awesome_teleop` 的新遥操作器。

#### 目录结构

以下是项目文件夹的外观。包名 `lerobot_teleoperator_my_awesome_teleop` 遵循了**规范 #1**。

```
lerobot_teleoperator_my_awesome_teleop/
├── pyproject.toml # (or setup.py) lists lerobot as a dependency
└── lerobot_teleoperator_my_awesome_teleop/
    ├── __init__.py
    ├── config_my_awesome_teleop.py
    └── my_awesome_teleop.py
```

#### 文件内容

* **`config_my_awesome_teleop.py`**：定义配置类。注意 `Config` 后缀（**规范 #2**）。

  ```
  from dataclasses import dataclass

  from lerobot.teleoperators.config import TeleoperatorConfig

  @TeleoperatorConfig.register_subclass("my_awesome_teleop")
  @dataclass
  class MyAwesomeTeleopConfig(TeleoperatorConfig):
      # Your configuration fields go here
      port: str = "192.168.1.1"
  ```
* **`my_awesome_teleop.py`**：实现设备。类名 `MyAwesomeTeleop` 与其配置类名称匹配（**规范 #2**）。此文件结构遵循**规范 #3**。

  ```
  from lerobot.teleoperators.teleoperator import Teleoperator

  from .config_my_awesome_teleop import MyAwesomeTeleopConfig

  class MyAwesomeTeleop(Teleoperator):
      config_class = MyAwesomeTeleopConfig
      name = "my_awesome_teleop"

      def __init__(self, config: MyAwesomeTeleopConfig):
          super().__init__(config)
          self.config = config

      # Your device logic (e.g., connect) goes here
  ```
* **`__init__.py`**：公开关键类（**规范 #4**）。

  ```
  from .config_my_awesome_teleop import MyAwesomeTeleopConfig
  from .my_awesome_teleop import MyAwesomeTeleop
  ```

### 安装与使用

1. **在您的 Python 环境中安装您的新插件。** 您可以使用 `pip` 的可编辑模式安装本地插件包，也可以从 PyPi 进行安装。

   ```
   # Locally
   # Navigate to your plugin's root directory and install it
   cd lerobot_teleoperator_my_awesome_teleop
   pip install -e .

   # From PyPi
   pip install lerobot_teleoperator_my_awesome_teleop
   ```
2. **直接从命令行使用。** 现在，您可以通过引用您的自定义设备类型来使用它。

   ```
   lerobot-teleoperate --teleop.type=my_awesome_teleop \
   # other arguments
   ```

就是这样！您的自定义设备现在已完全集成。

### 寻找示例？

看看这两个来自社区的包

* <https://github.com/SpesRobotics/lerobot-robot-xarm>
* <https://github.com/SpesRobotics/lerobot-teleoperator-teleop>

## 总结

一旦您的机器人类完成，您就可以利用 LeRobot 生态系统了

* 使用可用的遥操作器控制您的机器人，或直接集成您的遥操作设备
* 记录训练数据并将其可视化
* 将其集成到强化学习（RL）或模仿学习管线中

如需帮助，请随时在我们的 [Discord](https://discord.gg/s3KuuzsPFb) 上联系社区 🤗

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/integrate_hardware.mdx)
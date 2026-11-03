# 来源

https://hugging-face.cn/docs/lerobot/phone_teleop

# 手机

使用您的手机（iOS 或 Android）来控制机器人。

**在本指南中，您将学习：**

* 如何连接 iOS/Android 手机
* 手机姿态如何映射到机器人末端执行器（EE）目标
* 如何调整安全限制、夹爪控制和逆运动学（IK）设置

要使用手机控制您的机器人，请安装相关依赖：

```
pip install lerobot[phone]
```

## 快速入门

### 支持的平台

* iOS：使用 HEBI Mobile I/O 应用（ARKit 姿态 + 按钮）。请先下载该应用并打开，示例程序将通过网络发现它，并开始传输手机的姿态和输入数据。
* Android：使用 `teleop` 软件包（WebXR）。当您启动 Python 程序时，它会输出一个本地 URL。在手机上打开该链接，点击 Start，然后使用 Move 按钮即可传输姿态数据。

相关链接

* Android WebXR 库：[PyPI 上的 `teleop`](https://pypi.ac.cn/project/teleop/)
* iOS 应用：[HEBI Mobile I/O](https://docs.hebi.us/tools.html#mobile-io)

### 手机方向与控制

* 方向：握住手机，屏幕朝上，手机顶端指向与机器人夹爪相同的方向。这能确保校准后手机坐标系与机器人坐标系对齐，从而使运动感觉自然。参考下图。
* 启用/禁用
  + iOS：按住 `B1` 启用遥控，松开即可停止。首次按下时会捕获参考姿态。
  + Android：按住 `Move` 按钮，松开即可停止。首次按下时会捕获参考姿态。
* 夹爪控制
  + iOS：模拟输入 `A3` 控制夹爪的速度。
  + Android：按钮 `A` 和 `B` 充当增加/减少（A 打开，B 关闭）。您可以在 `GripperVelocityToJoint` 步骤中调整速度。

![Phone teleop orientation](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/phone_teleop.webp "Phone teleop orientation")

### 第一步：选择平台

修改示例，在 `PhoneConfig` 中使用 `PhoneOS.IOS` 或 `PhoneOS.ANDROID`。API 在各平台间通用，仅输入源不同。所有示例均位于 `examples/` 目录下，且提供 `phone_so100_*.py` 变体。

遥控示例

```
from lerobot.teleoperators.phone.config_phone import PhoneConfig, PhoneOS

teleop_config = PhoneConfig(phone_os=PhoneOS.IOS)  # or PhoneOS.ANDROID
teleop_device = Phone(teleop_config)
```

### 第二步：连接与校准

创建 `Phone(teleop_config)` 并调用 `connect()` 后，系统会自动提示校准。按上述姿势握住手机，然后：

* iOS：按住 `B1` 捕获参考姿态。
* Android：在 WebXR 页面上按 `Move` 按钮捕获参考姿态。

为什么要校准？我们捕获当前姿态，以便后续姿态均在对齐的机器人坐标系中表达。当您再次按下按钮启用控制时，位置会重新捕获，以防止手机在禁用期间位置移动导致的偏移。

### 第三步：运行示例

运行示例脚本即可进行遥控、录制数据集、回放数据集或评估策略。

所有脚本均假设您已配置好机器人（例如 SO-100 跟随者）并设置了正确的串口。

此外，您需要**将机器人的 URDF 文件复制到示例文件夹中**。对于本教程中的示例（使用 SO100/SO101），请从 [SO-ARM100 代码仓库](https://github.com/TheRobotStudio/SO-ARM100/blob/main/Simulation/SO101) 中将 `SO101` 文件夹复制到 `examples/phone_to_so100/` 目录下，这样 URDF 文件路径应为 `examples/phone_to_so100/SO101/so101_new_calib.urdf`。

* 运行此示例以进行遥控：

  ```
  cd examples/phone_to_so100
  python teleoperate.py
  ```

运行示例后：

* Android：启动脚本后，在手机上打开打印出的本地 URL，点击 Start，然后按住 Move 按钮。
* iOS：先打开 HEBI Mobile I/O；B1 用于启用运动，A3 控制夹爪。

此外，您可以通过编辑示例中展示的处理器步骤来自定义映射或安全限制。您还可以通过修改输入和运动学步骤，重新映射输入（例如使用不同的模拟输入）或将流水线适配到其他机器人（如 LeKiwi）。更多信息请参阅[机器人与遥控处理器](processors_robots_teleop.md)指南。

* 运行此示例以录制数据集，它会保存绝对末端执行器的观测值和动作。

  ```
  cd examples/phone_to_so100
  python record.py
  ```
* 运行此示例以回放录制的片段。

  ```
  cd examples/phone_to_so100
  python replay.py
  ```
* 运行此示例以评估预训练策略。

  ```
  cd examples/phone_to_so100
  python evaluate.py
  ```

### 重要的流水线步骤与选项

* 运动学应用于多个步骤。我们使用 [Placo](https://github.com/Rhoban/placo)（一个用于处理运动学的 Pinocchio 封装库）。我们通过传入机器人的 URDF 和目标坐标系来构建运动学对象，并将 `target_frame_name` 设置为夹爪坐标系。

  ```
  kinematics_solver = RobotKinematics(
    urdf_path="./SO101/so101_new_calib.urdf",
    target_frame_name="gripper_frame_link",
    joint_names=list(robot.bus.motors.keys()),
  )
  ```
* `MapPhoneActionToRobotAction` 步骤将校准后的手机姿态和输入转换为目标增量和夹爪指令；下方显示了该步骤的输出。

  ```
  action["enabled"] = enabled
        action["target_x"] = -pos[1] if enabled else 0.0
        action["target_y"] = pos[0] if enabled else 0.0
        action["target_z"] = pos[2] if enabled else 0.0
        action["target_wx"] = rotvec[1] if enabled else 0.0
        action["target_wy"] = rotvec[0] if enabled else 0.0
        action["target_wz"] = -rotvec[2] if enabled else 0.0
        action["gripper_vel"] = gripper_vel  # Still send gripper action when disabled
  ```
* `EEReferenceAndDelta` 步骤将目标增量转换为绝对目标末端执行器（EE）姿态，并在启用时存储一个参考点。`end_effector_step_sizes` 是 EE 姿态的步长，可以修改它来改变运动速度。

  ```
  EEReferenceAndDelta(
      kinematics=kinematics_solver,
      end_effector_step_sizes={"x": 0.5, "y": 0.5, "z": 0.5},
      motor_names=list(robot.bus.motors.keys()),
      use_latched_reference=True,
  ),
  ```
* `EEBoundsAndSafety` 步骤将 EE 运动限制在工作空间内，并检查大的 EE 步长跳变以确保安全。`end_effector_bounds` 是 EE 姿态的边界，可修改以改变工作空间；`max_ee_step_m` 是 EE 姿态的步长限制，可修改以改变安全限制。

  ```
  EEBoundsAndSafety(
      end_effector_bounds={"min": [-1.0, -1.0, -1.0], "max": [1.0, 1.0, 1.0]},
      max_ee_step_m=0.10,
  )
  ```
* `GripperVelocityToJoint` 步骤利用当前测量状态，将速度类夹爪输入转换为绝对夹爪位置。`speed_factor` 是速度的乘数。

  ```
  GripperVelocityToJoint(speed_factor=20.0)
  ```

#### 不同的逆运动学（IK）初始猜测

我们在运动学步骤中使用不同的 IK 初始猜测。初始猜测可以是当前测量的关节状态，也可以是上一次的 IK 解。

* 闭环（用于录制/评估）：设置 `initial_guess_current_joints=True`，使 IK 在每一帧都从测量的关节状态开始计算。

  ```
  InverseKinematicsEEToJoints(
      kinematics=kinematics_solver,
      motor_names=list(robot.bus.motors.keys()),
      initial_guess_current_joints=True,  # closed loop
  )
  ```
* 开环（用于回放）：设置 `initial_guess_current_joints=False`，使 IK 从上一次的计算结果继续计算，而不是从测量状态开始。这可以在无反馈回放时保持动作的稳定性。

  ```
  InverseKinematicsEEToJoints(
      kinematics=kinematics_solver,
      motor_names=list(robot.bus.motors.keys()),
      initial_guess_current_joints=False,  # open loop
  )
  ```

### 流水线步骤详解

* MapPhoneActionToRobotAction：将校准后的手机姿态和输入转换为目标增量和夹爪指令。运动由启用信号（iOS 上的 B1，Android 上的 Move）控制。
* EEReferenceAndDelta：在启用时锁定参考 EE 姿态，并将其与目标增量结合，在每一帧产生绝对目标 EE 姿态。禁用时，持续发送最后一次指令的姿态。
* EEBoundsAndSafety：将 EE 姿态锁定在工作空间内，并对跳变进行速率限制以确保安全。同时声明 `action.ee.*` 特征。
* InverseKinematicsEEToJoints：通过 IK 将 EE 姿态转换为关节位置。建议在闭环控制中设置 `initial_guess_current_joints=True`；若为了稳定性进行开环回放，请设为 `False`。
* GripperVelocityToJoint：利用当前测量状态，将类速度夹爪输入整合为绝对夹爪位置。
* ForwardKinematicsJointsToEE：从观测到的关节计算 `observation.state.ee.*`，用于日志记录和基于 EE 状态的训练。

### 疑难解答

* iOS 未发现设备：确保 HEBI Mobile I/O 已打开，且您的笔记本电脑与手机处于同一网络下。
* Android URL 无法访问：检查您是否使用了 `https` 而非 `http`，使用脚本打印出的确切 IP 地址，并允许您的浏览器忽略证书问题。
* 运动反向：在 `MapPhoneActionToRobotAction` 中调整符号翻转或交换轴，以匹配您的设置。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/phone_teleop.mdx)
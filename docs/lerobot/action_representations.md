# 来源

https://hugging-face.cn/docs/lerobot/action_representations

# 动作表示

本指南介绍了 LeRobot 中表示机器人动作的不同方式、它们之间的关联，以及每种方式的适用场景。

## 关节空间与末端执行器空间

在讨论动作表示之前，有必要了解动作可能存在的两个坐标空间。

### 关节空间 (Joint Space)

关节空间动作直接指定每个电机的目标位置。对于带抓取器的 6 自由度 (6-DOF) 机械臂，关节空间动作可能如下所示：

```
action = [shoulder_pan: 45.0, shoulder_lift: -20.0, elbow: -30.0, wrist_pitch: 10.0, wrist_roll: 0.0, wrist_yaw: 5.0, gripper: 0.8]
```

关节空间是 LeRobot 的默认设置。它简单易用，无需运动学模型，并可直接映射到电机指令。大多数入门级设置（如 SO-100、Koch）都使用关节空间动作。

### 末端执行器空间 (EE Space)

末端执行器空间动作通过笛卡尔坐标指定机器人工具头（抓取器）的目标位置和姿态。

```
action = [x: 0.25, y: -0.10, z: 0.15, wx: 0.0, wy: 0.0, wz: 0.1, gripper: 0.8]
```

对于“抓取并放置”(pick-and-place) 等任务，EE 空间更为直观，因为它直接描述了抓取器应到达的位置。但它需要运动学模型 (URDF) 来进行 EE 姿态与关节角度之间的转换。

### 空间转换

LeRobot 提供了用于关节空间和 EE 空间之间转换的处理器步骤，利用了正向和反向运动学。这些功能建立在 `RobotKinematics` 之上，它会加载机器人的 URDF 模型。

```
from lerobot.model.kinematics import RobotKinematics
from lerobot.robots.so_follower.robot_kinematic_processor import (
    ForwardKinematicsJointsToEE,
    InverseKinematicsEEToJoints,
)

kinematics = RobotKinematics(
    urdf_path="./SO101/so101_new_calib.urdf",
    target_frame_name="gripper_frame_link",
    joint_names=["shoulder", "elbow", "wrist_pitch", "wrist_roll", "wrist_yaw"],
)

# Joints → EE (for observations: "where is my gripper?")
fk_step = ForwardKinematicsJointsToEE(kinematics=kinematics, motor_names=[...])

# EE → Joints (for actions: "move my gripper here")
ik_step = InverseKinematicsEEToJoints(kinematics=kinematics, motor_names=[...])
```

请参阅 [`examples/so100\_to\_so100\_EE/`](https://github.com/huggingface/lerobot/tree/main/examples/so100_to_so100_EE) 获取在 SO-100 机械臂上使用 EE 空间动作进行记录、重放和评估的完整工作示例。

## 绝对动作、相对动作与增量动作

无论是在关节空间还是 EE 空间工作，动作值都可以通过三种方式表示。术语参考了 [UMI (Chi 等人, 2024)](https://arxiv.org/abs/2402.10329)。

### 绝对动作 (LeRobot 默认)

每个动作直接指定目标位置。

**示例**（关节空间，4 个动作的块/chunk）

```
current_state = [45.0, -30.0, 10.0]

action_chunk = [
    [46.0, -29.0, 11.0],   # go to 46, -29, 11
    [47.5, -27.0, 12.0],   # go to 47.5, -27, 12
    [49.0, -25.0, 13.5],   # go to 49, -25, 13.5
    [50.0, -24.0, 15.0],   # go to 50, -24, 15
]
```

每个值都是机器人坐标系中的目标位置。它简单直接，但要求全局坐标系保持一致。这是 LeRobot 中的默认设置。

### 相对动作 (由 OpenPI / pi0 使用)

块中的每个动作都是相对于**预测时刻当前状态**的偏移量。块中的所有动作共享同一个参考点。

```
current_state = [45.0, -30.0, 10.0]

relative_chunk = [
    [1.0,  1.0, 1.0],   # +1 from current → target 46, -29, 11
    [2.5,  3.0, 2.0],   # +2.5 from current → target 47.5, -27, 12
    [4.0,  5.0, 3.5],   # +4 from current → target 49, -25, 13.5
    [5.0,  6.0, 5.0],   # +5 from current → target 50, -24, 15
]
```

转换很简单：`相对值 = 绝对值 - 当前状态`。要恢复绝对值：`绝对值 = 相对值 + 当前状态`。

**为什么要使用相对动作？** 模型学习预测以零为中心的偏移量，这更容易归一化，并能带来更稳定的训练效果。由于每个块都参考相同的当前状态，因此不会在块之间累积误差。

### 增量动作 (顺序差值)

每个动作都是相对于**上一个动作**（或第一个步骤的当前状态）的偏移量。

```
current_state = [45.0, -30.0, 10.0]

delta_chunk = [
    [1.0,  1.0, 1.0],   # current → 46, -29, 11
    [1.5,  2.0, 1.0],   # previous action → 47.5, -27, 12
    [1.5,  2.0, 1.5],   # previous action → 49, -25, 13.5
    [1.0,  1.0, 1.5],   # previous action → 50, -24, 15
]
```

在这种模式下，每一步都相对于前一步。要恢复绝对位置，必须累加所有之前的增量，这意味着误差会随时间累积。UMI 正是因为这个原因明确反对使用这种表示方式。

### 视觉对比

下图（基于 [UMI, Chi 等人, 2024](https://arxiv.org/abs/2402.10329) 中的图示）阐明了关键区别。使用**相对轨迹**时，块中的每个动作都指向同一个起点（当前状态），因此新的推理步骤会清晰地重置参考点。使用**增量**时，每个动作都依赖于前一个动作，导致误差累积。**绝对**动作则要求一致的全局坐标系。

![Relative Trajectory as Action Representation (UMI, Chi et al., 2024)](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/action_representations_umi.png)

## 在 LeRobot 中使用相对动作

LeRobot 提供了 `RelativeActionsProcessorStep`，用于在处理器流水线中进行绝对动作和相对动作之间的转换。这也是 pi0、pi0.5 和 pi0\_fast 支持相对动作的方式。

> **注意：**所有 pi 模型（pi0、pi0.5、pi0\_fast）都会在归一化*之前*应用相对转换（`相对值 → 归一化`），因此归一化器总是接收增量（相对）值。这意味着当使用 `use\_relative\_actions=true` 进行训练时，所有这些模型都**需要相对动作统计数据**。在 pi0\_fast 中，`RelativeActionsProcessorStep` 仅修改动作——状态观测保持不变——因此 `NormalizerProcessorStep` 仍然在状态分词器之前运行，分词器也会按预期继续接收归一化后的状态。

### 工作原理

在**训练**（预处理）期间，动作在进入模型前会从绝对值转换为相对值。

```
raw absolute action → RelativeActionsProcessorStep → normalize → model
```

在**推理**（后处理）期间，模型预测结果在发送给机器人之前会转换回绝对值。

```
model output → unnormalize → AbsoluteActionsProcessorStep → robot
```

`AbsoluteActionsProcessorStep` 会从其配对的 `RelativeActionsProcessorStep` 读取缓存的当前状态，因此两者必须连接在一起（由策略工厂自动处理）。

### 为 pi 系列 (pi0, pi0.5, pi0\_fast) 启用相对动作

**第一步**：为数据集预计算相对动作统计数据。

```
lerobot-edit-dataset \
    --repo_id your_dataset \
    --operation.type recompute_stats \
    --operation.relative_action true \
    --operation.chunk_size 50 \
    --operation.relative_exclude_joints "['gripper']"
```

**第二步**：在启用相对动作的情况下进行训练。

```
lerobot-train \
    --dataset.repo_id=your_dataset \
    --policy.type=pi0 \
    --policy.use_relative_actions=true \
    --policy.relative_exclude_joints='["gripper"]'
```

`relative\_exclude\_joints` 参数用于指定应保持在绝对空间中的关节。例如，抓取器指令通常是二进制的（开/关），从相对编码中获益甚微。

### 将相对动作与 RTC 结合使用

[RTC](https://arxiv.org/abs/2506.07339) 以高频率运行策略推理，并按预测顺序将动作发送给机器人，而不是等待整个块生成完毕。相对动作与 RTC 完全兼容：因为在相对模式下，每个块都参考**相同**的当前状态（在推理开始时捕获），所以即使机器人已经移动，块中每个预测的动作仍保持有效的偏移量。无需特殊处理——`RelativeActionsProcessorStep` 在每次推理调用时缓存一次状态，而 `AbsoluteActionsProcessorStep` 会将其应用到流式输出中的每一个动作上。

### 将相对动作与 EE 空间结合使用

相对动作适用于关节空间和 EE 空间。例如，如果你的数据集存储的是 EE 动作，相对编码会将它们转换为相对于当前 EE 姿态的偏移量。

```
current_ee_state = [x: 0.25, y: -0.10, z: 0.15, gripper: 0.8]

absolute_ee_chunk = [
    [0.26, -0.09, 0.16, 0.8],
    [0.28, -0.07, 0.18, 0.8],
]

relative_ee_chunk = [
    [0.01,  0.01, 0.01, 0.0],   # offset from current EE pose
    [0.03,  0.03, 0.03, 0.0],   # offset from current EE pose
]
```

## 处理流水线总结

以下是不同处理器组合的方式。每个箭头代表一个处理器步骤，它们可以在 `RobotProcessorPipeline` 或 `PolicyProcessorPipeline` 中进行链接。

```
                    ┌─────────────────────────────────────────┐
   Action Space     │   Joint Space  ←──IK──→  EE Space      │
                    │   ForwardKinematicsJointsToEE           │
                    │   InverseKinematicsEEToJoints           │
                    └─────────────────────────────────────────┘

                    ┌─────────────────────────────────────────┐
   Representation   │   Absolute  ←────→  Relative            │
                    │   RelativeActionsProcessorStep (pre)    │
                    │   AbsoluteActionsProcessorStep (post)   │
                    └─────────────────────────────────────────┘

                    ┌─────────────────────────────────────────┐
   Normalization    │   Raw  ←────→  Normalized               │
                    │   NormalizerProcessorStep (pre)         │
                    │   UnnormalizerProcessorStep (post)      │
                    └─────────────────────────────────────────┘
```

典型的训练预处理器流程：`原始绝对关节动作 → 相对 → 归一化`。典型的推理后处理器流程：`反归一化 → 绝对 → （可选：逆运动学 IK 转换至关节）`。

## 参考文献

* [通用操作接口 (UMI)](https://arxiv.org/abs/2402.10329) - Chi 等人, 2024。定义了相对轨迹动作表示，并将其与绝对动作和增量动作进行了比较。
* [处理器简介](introduction_processors.md) - LeRobot 中处理器流水线的工作原理。
* [`examples/so100\_to\_so100\_EE/`](https://github.com/huggingface/lerobot/tree/main/examples/so100_to_so100_EE) - 使用 EE 空间动作进行记录和评估的完整示例。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/action_representations.mdx)
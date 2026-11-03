# 来源

https://hugging-face.cn/docs/lerobot/processors_robots_teleop

# 机器人与远程操作员处理器

本指南将介绍如何构建和修改处理流水线（processing pipelines），以将远程操作设备（如手机）连接到机器人和数据集。流水线使不同动作/观察空间之间的转换标准化，因此您可以更换远程操作设备和机器人而无需重写胶水代码。

为了具体起见，我们使用“手机到 SO-100 跟随者”的示例，但相同的模式也适用于其他机器人。

**你将学到什么**

* 绝对 EE 控制 vs 相对 EE 控制：各自的含义、权衡以及如何根据您的任务进行选择。
* 三流水线模式：如何将 远程操作动作 $\rightarrow$ 数据集动作 $\rightarrow$ 机器人指令，以及 机器人观察 $\rightarrow$ 数据集观察 进行映射。
* 适配器 (`to_transition` / `to_output`)：这些适配器如何将原始字典转换为 `EnvTransition` 及其逆向转换，以减少样板代码。
* 数据集特征契约：步骤如何通过 `transform_features(...)` 声明特征，以及如何为了记录而聚合/合并这些特征。
* 选择表示形式：何时存储关节角度、绝对 EE 位姿或相对 EE 增量——以及这将如何影响训练。
* 流水线自定义指南：如何安全地更换机器人/URDF，并调整边界、步长以及 IK 初始化等选项。

### 绝对 EE 控制 vs 相对 EE 控制

本指南中的示例使用了绝对末端执行器 (EE) 位姿，因为它们易于推导。在实践中，相对 EE 增量或关节位置通常被作为首选的学习特征。

通过处理器，您可以选择想要用于策略的学习特征。这可以是关节位置/速度、绝对 EE 或相对 EE 位置。您还可以选择存储其他特征，例如关节力矩、电机电流等。

## 三条流水线

我们经常组合三条流水线。根据您的设置，如果动作和观察空间已经匹配，其中某些流水线可以是空的。每条流水线处理不同动作空间和观察空间之间的不同转换。以下是对每条流水线的简要说明。

1. 流水线 1：远程操作动作空间 $\rightarrow$ 数据集动作空间 (手机位姿 $\rightarrow$ EE 目标)
2. 流水线 2：数据集动作空间 $\rightarrow$ 机器人指令空间 (EE 目标 $\rightarrow$ 关节角度)
3. 流水线 3：机器人观察空间 $\rightarrow$ 数据集观察空间 (关节角度 $\rightarrow$ EE 位姿)

以下是在“手机到 SO-100 跟随者”示例中使用的三条流水线示例

```
phone_to_robot_ee_pose_processor = RobotProcessorPipeline[RobotAction, RobotAction]( # teleop -> dataset action
    steps=[
        MapPhoneActionToRobotAction(platform=teleop_config.phone_os),
        EEReferenceAndDelta(
            kinematics=kinematics_solver, end_effector_step_sizes={"x": 0.5, "y": 0.5, "z": 0.5}, motor_names=list(robot.bus.motors.keys()),
        ),
        EEBoundsAndSafety(
            end_effector_bounds={"min": [-1.0, -1.0, -1.0], "max": [1.0, 1.0, 1.0]}, max_ee_step_m=0.20,
        ),
        GripperVelocityToJoint(),
    ],
    to_transition=robot_action_to_transition,
    to_output=transition_to_robot_action,
)

robot_ee_to_joints_processor = RobotProcessorPipeline[RobotAction, RobotAction]( # dataset action -> robot
    steps=[
        InverseKinematicsEEToJoints(
            kinematics=kinematics_solver, motor_names=list(robot.bus.motors.keys()), initial_guess_current_joints=True,
        ),
    ],
    to_transition=robot_action_to_transition,
    to_output=transition_to_robot_action,
)

robot_joints_to_ee_pose = RobotProcessorPipeline[RobotObservation, RobotObservation]( # robot obs -> dataset obs
    steps=[
        ForwardKinematicsJointsToEE(kinematics=kinematics_solver, motor_names=list(robot.bus.motors.keys()))
    ],
    to_transition=observation_to_transition,
    to_output=transition_to_observation,
)
```

## 为什么需要 to\_transition / to\_output

为了在机器人/远程操作员与流水线之间进行双向转换，我们使用 `to_transition` 和 `to_output` 流水线适配器。它们将转换标准化以减少样板代码，并构成了机器人和远程操作员的原始字典与流水线 `EnvTransition` 格式之间的桥梁。在“手机到 SO-100 跟随者”示例中，我们使用以下适配器：

* `robot_action_to_transition`：将远程操作动作字典转换为流水线转换 (transition)。
* `transition_to_robot_action`：将流水线转换转换为机器人动作字典。
* `observation_to_transition`：将机器人观察字典转换为流水线转换。
* `transition_to_observation`：将流水线转换转换为观察字典。

更多详情请参阅 [src/lerobot/processor/converters.py](https://github.com/huggingface/lerobot/blob/main/src/lerobot/processor/converters.py)。

## 数据集特征契约

数据集特征由保存在数据集中的键决定。每个步骤可以通过名为 `transform_features(...)` 的契约声明它修改了哪些特征。一旦您构建了处理器，处理器就可以使用 `aggregate_pipeline_dataset_features()` 聚合所有这些特征，并使用 `combine_feature_dicts(...)` 合并多个特征字典。

以下是在“手机到 SO-100 跟随者”示例中如何使用 `transform_features` 方法声明特征的示例

```
    def transform_features(
        self, features: dict[PipelineFeatureType, dict[str, PolicyFeature]]
    ) -> dict[PipelineFeatureType, dict[str, PolicyFeature]]:
        # We only use the ee pose in the dataset, so we don't need the joint positions
        for n in self.motor_names:
            features[PipelineFeatureType.ACTION].pop(f"{n}.pos", None)
        # We specify the dataset features of this step that we want to be stored in the dataset
        for k in ["x", "y", "z", "wx", "wy", "wz", "gripper_pos"]:
            features[PipelineFeatureType.ACTION][f"ee.{k}"] = PolicyFeature(
                type=FeatureType.STATE, shape=(1,)
            )
        return features
```

在这里，我们声明在此步骤中修改了哪些 PolicyFeatures，这样我们就知道在运行处理器时可以预期哪些特征。这些特征随后可以被聚合并用于创建数据集特征。

以下是在“手机到 SO-100 记录”示例中我们如何聚合和合并特征的示例

```
features=combine_feature_dicts(
        # Run the feature contract of the pipelines
        # This tells you how the features would look like after the pipeline steps
        aggregate_pipeline_dataset_features(
            pipeline=phone_to_robot_ee_pose_processor,
            initial_features=create_initial_features(action=phone.action_features), # <- Action features we can expect, these come from our teleop device (phone) and action processor
            use_videos=True,
        ),
        aggregate_pipeline_dataset_features(
            pipeline=robot_joints_to_ee_pose,
            initial_features=create_initial_features(observation=robot.observation_features), # <- Observation features we can expect, these come from our robot and observation processor
            use_videos=True,
            patterns=["observation.state.ee"], # <- Here you could optionally filter the features we want to store in the dataset, with a specific pattern

        ),
    ),
```

工作原理

* `aggregate_pipeline_dataset_features(...)`：在整个流水线中应用 `transform_features` 并通过模式进行过滤（当 `use_videos=True` 时包含图像，当指定 `patterns` 时包含状态特征）。
* `combine_feature_dicts(...)`：合并多个特征字典。
* 使用 `record_loop(...)` 进行记录时，会使用 `build_dataset_frame(...)` 来构建与 `dataset.features` 一致的帧，然后在调用 `add_frame(...)` 将帧添加到数据集中。

## 自定义机器人流水线指南

您可以将以下任何特征存储为您的动作/观察空间：

* 关节位置
* 绝对 EE 位姿
* 相对 EE 增量
* 其他特征：关节速度、力矩等。

选择您想要用于策略动作和观察空间的特征，并相应地配置/修改流水线和步骤。

### 不同机器人

* 您可以轻松复用流水线。例如，要使用另一个机器人配合手机远程操作，请修改示例并更换机器人的 `RobotKinematics` (URDF) 和 `motor_names`。此外，您应确保 `target_frame_name` 指向您的夹持器/腕部。

### 安全第一

* 在更改流水线时，请从严格的边界限制开始，在操作真实机器人时实施安全步骤。
* 建议先从仿真开始，然后再迁移到真实机器人。

就到这里！我们希望本指南能帮助您开始自定义机器人流水线。如果您在任何环节遇到问题，请加入我们的 [Discord 社区](https://discord.com/invite/s3KuuzsPFb) 寻求支持。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/processors_robots_teleop.mdx)
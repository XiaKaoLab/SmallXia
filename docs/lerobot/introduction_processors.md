# 来源

https://hugging-face.cn/docs/lerobot/introduction_processors

# 处理器介绍

在机器人技术中，机器人和人类产生的数据与机器学习模型所期望的数据之间存在根本性的不匹配。机器人输出原始传感器数据（如摄像机图像和关节位置），在模型处理这些数据之前，需要进行归一化、批处理和设备放置。人类的语言指令必须被分词为数值表示，且不同的机器人使用需要标准化的不同坐标系。

这一挑战也延伸到了模型输出端。模型可能输出末端执行器的位置，而机器人需要的是关节空间指令；或者远程操作员产生的是相对运动，而机器人期望的是绝对指令。模型预测通常是归一化的，需要转换回现实世界的尺度。

跨域转换增加了另一层复杂性。来自一个机器人装置的训练数据需要适配到不同的硬件上进行部署，针对特定摄像机配置训练的模型必须能够适应新的布局，而具有不同命名约定的数据集也需要进行协调。

**这就是处理器的用武之地。** 它们充当通用翻译器，弥合这些差距，确保数据从传感器到模型再到执行器的顺畅流动。处理器处理将原始环境数据转换为模型就绪输入（反之亦然）所需的所有预处理和后处理步骤。

这意味着您喜爱的策略可以这样使用

```
import torch

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.policies.factory import make_pre_post_processors
from lerobot.policies.your_policy import YourPolicy
from lerobot.processor.pipeline import RobotProcessorPipeline, PolicyProcessorPipeline
dataset = LeRobotDataset("hf_user/dataset", episodes=[0])
sample = dataset[10]

model = YourPolicy.from_pretrained(
    "hf_user/model",
)
model.eval()
model.to("cuda")
preprocessor, postprocessor = make_pre_post_processors(model.config, pretrained_path="hf_user/model", dataset_stats=dataset.meta.stats)

preprocessed_sample = preprocessor(sample)
action = model.select_action(preprocessed_sample)
postprocessed_action = postprocessor(action)
```

## 什么是处理器？

在机器人技术中，数据形式多样：摄像机图像、传感器关节位置、用户文本指令等。每种类型的数据都需要特定的转换，模型才能有效地使用它。模型需要这些数据满足以下条件：

* **归一化（Normalized）**：缩放到适合神经网络处理的范围
* **批处理（Batched）**：组织成适合批处理的维度
* **分词（Tokenized）**：文本转换为数值表示
* **设备放置（Device-placed）**：移动到正确的硬件（CPU/GPU）
* **类型转换（Type-converted）**：转换为适当的数据类型

处理器通过可组合、可重用的步骤来处理这些转换，这些步骤可以串联成流水线。您可以将其想象成一条模块化装配线，每个工位对您的数据执行特定的转换。

## 核心概念

### EnvTransition：通用数据容器

`EnvTransition` 是在所有处理器中流动的基本数据结构。它是一个类型化字典，表示完整的机器人与环境交互：

* **OBSERVATION（观测）**：所有传感器数据（图像、状态、本体感受）
* **ACTION（动作）**：要执行或已执行的动作
* **REWARD（奖励）**：强化学习信号
* **DONE/TRUNCATED（完成/截断）**：回合边界指标
* **INFO（信息）**：任意元数据
* **COMPLEMENTARY\_DATA（补充数据）**：任务描述、索引、填充标志、步间数据

### ProcessorStep：构建基块

`ProcessorStep` 是处理转换的单个转换单元。它是一个具有两个必需方法的抽象基类：

```
from lerobot.processor import ProcessorStep, EnvTransition

class MyProcessorStep(ProcessorStep):
    """Example processor step - inherit and implement abstract methods."""

    def __call__(self, transition: EnvTransition) -> EnvTransition:
        """Transform the transition - REQUIRED abstract method."""
        # Your processing logic here
        return transition

    def transform_features(self, features):
        """Declare how this step transforms feature shapes/types - REQUIRED abstract method."""
        return features  # Most processors return features unchanged
```

`__call__` 是处理器步骤的核心。它接收一个 `EnvTransition` 并返回一个修改后的 `EnvTransition`。

`transform_features` 用于声明此步骤如何转换特征形状/类型。

### DataProcessorPipeline：通用编排器

`DataProcessorPipeline[TInput, TOutput]` 将多个 `ProcessorStep` 实例串联在一起。

```
from lerobot.processor import RobotProcessorPipeline, PolicyProcessorPipeline

# For robot hardware (unbatched data)
robot_processor = RobotProcessorPipeline[RobotAction, RobotAction](
    steps=[step1, step2, step3],
    name="robot_pipeline"
)

# For model training/inference (batched data)
policy_processor = PolicyProcessorPipeline[dict[str, Any], dict[str, Any]](
    steps=[step1, step2, step3],
    name="policy_pipeline"
)
```

## RobotProcessorPipeline 与 PolicyProcessorPipeline

关键区别在于它们处理的数据结构：

| 方面 | RobotProcessorPipeline | PolicyProcessorPipeline |
| --- | --- | --- |
| **输入** | `dict[str, Any]` - 独立的机器人数值 | `dict[str, Any]` - 批处理张量 |
| **输出** | `dict[str, Any]` - 独立的机器人命令 | `torch.Tensor` - 策略预测 |
| **用例** | 实时机器人控制 | 模型训练/推理 |
| **数据格式** | 非批处理，异构 | 批处理，同构 |
| **示例** | `{"joint_1": 0.5}` | `{"observation.state": tensor([[0.5]])}` |

**使用 `RobotProcessorPipeline`** 处理机器人硬件接口

```
# Robot data structures: dict[str, Any] for observations and actions
robot_obs: dict[str, Any] = {
    "joint_1": 0.5,           # Individual joint values
    "joint_2": -0.3,
    "camera_0": image_array   # Raw camera data
}

robot_action: dict[str, Any] = {
    "joint_1": 0.2,          # Target joint positions
    "joint_2": 0.1,
    "gripper": 0.8
}
```

**使用 `PolicyProcessorPipeline`** 进行模型训练和批处理

```
# Policy data structures: batch dicts and tensors
policy_batch: dict[str, Any] = {
    "observation.state": torch.tensor([[0.5, -0.3]]),      # Batched states
    "observation.images.camera0": torch.tensor(...),        # Batched images
    "action": torch.tensor([[0.2, 0.1, 0.8]])              # Batched actions
}

policy_action: torch.Tensor = torch.tensor([[0.2, 0.1, 0.8]])  # Model output tensor
```

## 转换器函数

LeRobot 在 `lerobot.processor.converters` 中提供了转换器函数，用于连接不同的数据格式。这些函数处理机器人硬件数据结构、策略模型格式以及在处理器流水线中流动的内部 `EnvTransition` 表示之间的关键转换。

| 类别 | 函数 | 描述 |
| --- | --- | --- |
| **机器人硬件转换器** | `robot_action_to_transition` | 机器人字典 → EnvTransition |
|  | `observation_to_transition` | 机器人观测 → EnvTransition |
|  | `transition_to_robot_action` | EnvTransition → 机器人字典 |
| **策略/训练转换器** | `batch_to_transition` | 批处理字典 → EnvTransition |
|  | `transition_to_batch` | EnvTransition → 批处理字典 |
|  | `policy_action_to_transition` | 策略张量 → EnvTransition |
|  | `transition_to_policy_action` | EnvTransition → 策略张量 |
| **实用工具** | `create_transition` | 使用默认值构建转换 |
|  | `identity_transition` | 直通转换器 |

关键的见解是：**机器人硬件转换器**处理的是单个值和字典，而**策略/训练转换器**处理的是批处理张量和模型输出。转换器函数会自动处理结构差异，因此您的处理器步骤可以专注于核心转换，而不必担心数据格式兼容性。

## 处理器示例

以下示例演示了用于策略训练和推理的实际处理器配置。

这是一个用于策略训练和推理的示例处理器

```
# Training data preprocessing (optimized order for GPU performance)
training_preprocessor = PolicyProcessorPipeline[dict[str, Any], dict[str, Any]](
    steps=[
        RenameObservationsProcessorStep(rename_map={}),     # Standardize keys
        AddBatchDimensionProcessorStep(),                   # Add batch dims
        TokenizerProcessorStep(tokenizer_name="...", ...),  # Tokenize language
        DeviceProcessorStep(device="cuda"),                 # Move to GPU first
        NormalizerProcessorStep(features=..., stats=...),   # Normalize on GPU
    ]
)

# Model output postprocessing
training_postprocessor = PolicyProcessorPipeline[torch.Tensor, torch.Tensor](
    steps=[
        DeviceProcessorStep(device="cpu"),                  # Move to CPU
        UnnormalizerProcessorStep(features=..., stats=...), # Denormalize
    ]
    to_transition=policy_action_to_transition,
    to_output=transition_to_policy_action,
)
```

### 机器人与策略之间通过处理器进行的交互

最常见的现实场景是结合了两种流水线类型：机器人硬件生成需要策略处理的观测，而策略输出需要机器人兼容的后处理。

```
# Real deployment: Robot sensors → Model → Robot commands
with torch.no_grad():
    while not done:
        raw_obs = robot.get_observation()  # dict[str, Any]

        # Add your robot observation to policy observation processor

        policy_input = policy_preprocessor(raw_obs)  # Batched dict

        policy_output = policy.select_action(policy_input)  # Policy tensor

        policy_action = policy_postprocessor(policy_output)

        # Add your robot action to policy action processor

        robot.send_action(policy_action)
```

## 特征契约：形状和类型转换

处理器不仅可以转换数据，还可以**改变数据结构本身**。`transform_features()` 方法声明这些更改，这对于数据集记录和策略创建至关重要。

### 为什么特征契约很重要

在构建数据集或策略时，LeRobot 需要知道：

* **处理后将存在哪些数据字段**
* **每个字段将具有哪些形状和类型**
* **如何为预期的数据结构配置模型**

```
# Example: A processor that adds velocity to observations
class VelocityProcessor(ObservationProcessorStep):
    def observation(self, obs):
        new_obs = obs.copy()
        if "observation.state" in obs:
            # concatenate computed velocity field to the state
            new_obs["observation.state"] = self._compute_velocity(obs["observation.state"])
        return new_obs

    def transform_features(self, features):
        """Declare the new velocity field we're adding."""
        state_feature = features[PipelineFeatureType.OBSERVATION].get("observation.state")
        if state_feature:
            double_shape = (state_feature.shape[0] * 2,) if state_feature.shape else (2,)
            features[PipelineFeatureType.OBSERVATION]["observation.state"] = PolicyFeature(
                type=FeatureType.STATE, shape=double_shape
            )
        return features
```

### 特征规范函数

`create_initial_features()` 和 `aggregate_pipeline_dataset_features()` 解决了数据集创建中的一个关键问题：在处理任何数据之前确定最终的确切数据结构。由于处理器流水线可以添加新特征（如速度字段）、更改张量形状（如裁剪图像）或重命名键，数据集需要预先知道完整的输出规范，以便分配适当的存储空间并定义模式。这些函数通过从机器人硬件规范（`create_initial_features()`）开始，然后模拟整个流水线转换（`aggregate_pipeline_dataset_features()`），来计算传递给 `LeRobotDataset.create()` 的最终特征字典，从而确保处理器输出与数据集预期存储的内容之间完全对齐。

```
from lerobot.datasets.pipeline_features import aggregate_pipeline_dataset_features

# Start with robot's raw features
initial_features = create_initial_features(
    observation=robot.observation_features,  # {"joint_1.pos": float, "camera_0": (480,640,3)}
    action=robot.action_features            # {"joint_1.pos": float, "gripper.pos": float}
)

# Apply processor pipeline to compute final features
final_features = aggregate_pipeline_dataset_features(
    pipeline=my_processor_pipeline,
    initial_features=initial_features,
    use_videos=True
)

# Use for dataset creation
dataset = LeRobotDataset.create(
    repo_id="my_dataset",
    features=final_features,  # Knows exactly what data to expect
    ...
)
```

## 常见处理器步骤

LeRobot 提供了许多已注册的处理器步骤。以下是最常用的核心处理器：

### 基础处理器

* **`normalizer_processor`**：使用数据集统计信息（均值/标准差或最小值/最大值）归一化观测/动作
* **`device_processor`**：将张量移动到 CPU/GPU，并可选择进行 dtype 转换
* **`to_batch_processor`**：向转换中添加批维度以实现模型兼容性
* **`rename_observations_processor`**：使用映射字典重命名观测键
* **`tokenizer_processor`**：将自然语言任务描述分词为 token 和注意力掩码

### 后续步骤

* **[实现您自己的处理器](implement_your_own_processor.md)** - 创建自定义处理器步骤
* **[调试您的流水线](debug_processor_pipeline.md)** - 对流水线进行故障排除和优化
* **[机器人和远程操作员的处理器](processors_robots_teleop.md)** - 现实世界集成模式

## 总结

处理器通过提供以下功能来解决机器人技术中的数据转换问题：

* **模块化转换**：可组合、可重用的处理步骤
* **类型安全**：具有编译时检查的通用流水线
* **性能优化**：GPU 加速操作
* **机器人/策略区分**：针对不同数据结构的独立流水线
* **综合生态系统**：30+ 个用于常见任务的已注册处理器

关键见解：`RobotProcessorPipeline` 处理非批处理的机器人硬件数据，而 `PolicyProcessorPipeline` 处理批处理的模型数据。为您的数据结构选择正确的工具！

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/introduction_processors.mdx)
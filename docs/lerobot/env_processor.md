# 来源

https://hugging-face.cn/docs/lerobot/env_processor

# 环境处理器

环境处理器是 LeRobot 数据处理架构中的关键层，负责处理**特定于环境**的转换，与特定于策略的处理分离开来。这种关注点分离实现了更简洁的代码、更好的模块化，并能更轻松地针对不同环境和策略进行实验。

## 为什么需要环境处理器？

在使用不同的机器人环境（LIBERO、MetaWorld、Aloha 等）时，每个环境通常都有独特的数据格式、坐标系和规范，需要在策略处理**之前**进行标准化。如果没有环境处理器，这些转换将：

1. **硬编码在环境代码中** - 使得尝试不同的状态表示变得困难
2. **在各策略中重复** - 每个策略都需要处理特定于环境的怪癖
3. **与策略逻辑混合** - 违反了关注点分离原则，增加了调试难度

环境处理器通过在原始环境观测和策略输入之间提供一个**专门的处理层**来解决这些问题。

## 处理流水线

以下是评估过程中数据在完整处理流水线中的流动方式

```
# In lerobot_eval.py rollout() function:

# 1. Raw environment observation (numpy arrays, various formats)
raw_observation = env.step(action)

# 2. Convert numpy to torch, normalize images [0,1]
observation = preprocess_observation(raw_observation)

# 3. Add task metadata (for multi-task environments)
observation = add_envs_task(env, observation)

# 4. ENVIRONMENT-SPECIFIC preprocessing (NEW!)
#    - Flatten robot states
#    - Rotate images to match dataset conventions
#    - Handle environment-specific coordinate systems
observation = env_preprocessor(observation)

# 5. POLICY-SPECIFIC preprocessing
#    - Normalize with dataset statistics
#    - Add batch dimensions
#    - Move to GPU
#    - Tokenize language instructions
observation = preprocessor(observation)

# 6. Policy inference
action = policy.select_action(observation)

# 7. POLICY-SPECIFIC postprocessing
#    - Unnormalize actions
#    - Remove batch dimensions
action = postprocessor(action)

# 8. ENVIRONMENT-SPECIFIC postprocessing (NEW!)
#    - Convert action formats if needed
#    - Apply environment-specific constraints
action_transition = {"action": action}
action_transition = env_postprocessor(action_transition)
action = action_transition["action"]

# 9. Execute in environment
env.step(action)
```

## 优势

### 1. 关注点分离

环境处理器负责处理特定于**环境数据格式**的转换，而策略处理器负责处理特定于**模型需求**的转换。

```
# ❌ Before: Mixed concerns
class LiberoVLAPolicy:
    def preprocess(self, obs):
        # Environment-specific: Flatten robot state (shouldn't be in policy!)
        state = self._flatten_robot_state(obs["robot_state"])
        # Policy-specific: Normalize with dataset stats
        state = self.normalizer(state)
        return state

# ✅ After: Clear separation
# Environment processor: Handles LIBERO's nested robot state
env_preprocessor = LiberoProcessorStep()  # Flattens robot_state

# Policy processor: Handles model requirements
policy_preprocessor = NormalizerProcessorStep(stats=dataset_stats)
```

### 2. 灵活性与可重用性

相同的策略可以与不同的环境处理器协同工作，同样，相同的环境处理器也可以与不同的策略协同工作。

```
# Use SmolVLA policy with LIBERO environment
libero_preprocessor, libero_postprocessor = make_env_pre_post_processors(libero_cfg)
smolvla_preprocessor, smolvla_postprocessor = make_pre_post_processors(smolvla_cfg)

# Or use ACT policy with the same LIBERO environment
libero_preprocessor, libero_postprocessor = make_env_pre_post_processors(libero_cfg)
act_preprocessor, act_postprocessor = make_pre_post_processors(act_cfg)
```

### 3. 更简便的实验

想为 LIBERO 尝试不同的状态表示吗？只需创建一个新的处理器即可。

```
# Original: 8D state (pos + quat→axisangle + gripper)
@ProcessorStepRegistry.register("libero_processor")
class LiberoProcessorStep(ObservationProcessorStep):
    def _process_observation(self, obs):
        eef_pos = robot_state["eef"]["pos"]          # 3D
        eef_axisangle = quat2axisangle(quat)         # 3D
        gripper = robot_state["gripper"]["qpos"]     # 2D
        state = torch.cat([eef_pos, eef_axisangle, gripper], dim=-1)  # 8D
        return state

# Experiment: Add velocity for better control
@ProcessorStepRegistry.register("libero_velocity_processor")
class LiberoVelocityProcessorStep(ObservationProcessorStep):
    def _process_observation(self, obs):
        # Include velocities for 14D state
        eef_pos = robot_state["eef"]["pos"]          # 3D
        eef_axisangle = quat2axisangle(quat)         # 3D
        eef_vel = robot_state["eef"]["vel"]          # 3D  (NEW)
        gripper_pos = robot_state["gripper"]["qpos"] # 2D
        gripper_vel = robot_state["gripper"]["qvel"] # 3D  (NEW)
        state = torch.cat([eef_pos, eef_axisangle, eef_vel,
                          gripper_pos, gripper_vel], dim=-1)  # 14D
        return state
```

### 4. 更简洁的环境代码

环境可以公开**所有可用数据**，而无需预知下游模型将使用哪些数据。

```
# LIBERO environment exposes full robot state
observation = {
    "pixels": {"image": img, "image2": img2},
    "robot_state": {
        "eef": {"pos": ..., "quat": ..., "vel": ..., "mat": ..., "axisangle": ...},
        "gripper": {"qpos": ..., "qvel": ...},
        "joints": {"pos": ..., "vel": ...}
    }
}

# Environment processor decides what to use
# Policy processor handles model-specific transformations
```

## 使用环境处理器

### 工厂函数

`make_env_pre_post_processors` 函数遵循与策略的 `make_pre_post_processors` 相同的模式。

```
from lerobot.envs.factory import make_env_pre_post_processors
from lerobot.envs.configs import LiberoEnv, PushtEnv

# For LIBERO: Returns LiberoProcessorStep in preprocessor
libero_cfg = LiberoEnv(task="libero_spatial", camera_name=["agentview"])
env_preprocessor, env_postprocessor = make_env_pre_post_processors(libero_cfg)

# For other environments: Returns identity processors (no-op)
pusht_cfg = PushtEnv()
env_preprocessor, env_postprocessor = make_env_pre_post_processors(pusht_cfg)
```

### 在 envs/factory.py 中的实现

```
def make_env_pre_post_processors(
    env_cfg: EnvConfig,
) -> tuple[
    PolicyProcessorPipeline[dict[str, Any], dict[str, Any]],
    PolicyProcessorPipeline[dict[str, Any], dict[str, Any]],
]:
    """
    Create preprocessor and postprocessor pipelines for environment observations.

    Args:
        env_cfg: The configuration of the environment.

    Returns:
        A tuple containing:
            - preprocessor: Pipeline that processes environment observations
            - postprocessor: Pipeline that processes environment outputs
    """
    # For LIBERO environments, add the LiberoProcessorStep to preprocessor
    if isinstance(env_cfg, LiberoEnv) or "libero" in env_cfg.type:
        preprocessor = PolicyProcessorPipeline(steps=[LiberoProcessorStep()])
    else:
        # For all other environments, return an identity preprocessor
        preprocessor = PolicyProcessorPipeline(steps=[])

    # Postprocessor is currently identity for all environments
    # Future: Could add environment-specific action transformations
    postprocessor = PolicyProcessorPipeline(steps=[])

    return preprocessor, postprocessor
```

### 在评估中的集成

在 `lerobot_eval.py` 中，环境处理器会创建一次并在整个过程中使用。

```
def eval_main(cfg: EvalPipelineConfig):
    # Create environment
    envs = make_env(cfg.env, n_envs=cfg.eval.batch_size)

    # Create policy
    policy = make_policy(cfg=cfg.policy, env_cfg=cfg.env)

    # Create policy processors
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=cfg.policy,
        pretrained_path=cfg.policy.pretrained_path,
    )

    # Create environment processors (NEW!)
    env_preprocessor, env_postprocessor = make_env_pre_post_processors(env_cfg=cfg.env)

    # Run evaluation with both processor types
    eval_policy_all(
        envs=envs,
        policy=policy,
        env_preprocessor=env_preprocessor,      # Environment-specific
        env_postprocessor=env_postprocessor,    # Environment-specific
        preprocessor=preprocessor,              # Policy-specific
        postprocessor=postprocessor,            # Policy-specific
        n_episodes=cfg.eval.n_episodes,
    )
```

## 示例：LIBERO 环境处理器

`LiberoProcessorStep` 展示了一个实际的环境处理器示例。

```
from lerobot.processor.pipeline import ObservationProcessorStep

@dataclass
@ProcessorStepRegistry.register(name="libero_processor")
class LiberoProcessorStep(ObservationProcessorStep):
    """
    Processes LIBERO observations into the LeRobot format.

    **State Processing:**
    - Extracts end-effector position (3D)
    - Converts quaternion to axis-angle representation (3D)
    - Extracts gripper joint positions (2D)
    - Concatenates into 8D state vector

    **Image Processing:**
    - Rotates images 180° to match HuggingFaceVLA/libero convention
    """

    def _process_observation(self, observation):
        processed_obs = observation.copy()

        # Process images: Flip 180° for camera convention
        for key in list(processed_obs.keys()):
            if key.startswith("observation.images."):
                img = processed_obs[key]
                img = torch.flip(img, dims=[2, 3])  # Flip H and W
                processed_obs[key] = img

        # Process robot_state: Flatten to 8D vector
        if "observation.robot_state" in processed_obs:
            robot_state = processed_obs.pop("observation.robot_state")

            eef_pos = robot_state["eef"]["pos"]           # (B, 3)
            eef_quat = robot_state["eef"]["quat"]         # (B, 4)
            gripper_qpos = robot_state["gripper"]["qpos"] # (B, 2)

            # Convert quaternion to axis-angle
            eef_axisangle = self._quat2axisangle(eef_quat)  # (B, 3)

            # Concatenate into single state vector
            state = torch.cat((eef_pos, eef_axisangle, gripper_qpos), dim=-1)
            state = state.float()

            processed_obs["observation.state"] = state

        return processed_obs
```

### 为什么要进行这些转换？

1. **图像旋转**：HuggingFaceVLA/libero 数据集中的图像相对于原始 LIBERO 模拟器旋转了 180°。该处理器处理了这种规范不匹配，使得在数据集上训练的策略能够顺畅运行。
2. **状态扁平化**：原始 LIBERO 环境公开了包含所有可用状态信息（位置、四元数、速度、矩阵表示等）的嵌套字典。处理器：

   * 选择相关组件（位置、四元数、夹爪）
   * 将四元数转换为轴角表示（更适合学习）
   * 扁平化为策略所期望的单个 8D 向量
3. **灵活性**：环境仍然公开了**所有**原始数据。如果您想尝试不同的状态表示（例如，包含速度、使用矩阵表示而不是轴角），您可以创建一个新的处理器，而无需修改环境代码。

## 为新环境添加环境处理器

要为新环境添加环境处理器，请执行以下步骤：

### 1. 创建处理器步骤

```
# In src/lerobot/processor/env_processor.py

@dataclass
@ProcessorStepRegistry.register(name="myenv_processor")
class MyEnvProcessorStep(ObservationProcessorStep):
    """Process observations from MyEnv."""

    def _process_observation(self, observation):
        processed = observation.copy()

        # Your environment-specific transformations
        if "myenv.specific.state" in processed:
            state = processed.pop("myenv.specific.state")
            # Transform to standard format
            processed["observation.state"] = self._transform_state(state)

        return processed
```

### 2. 更新工厂

```
# In src/lerobot/envs/factory.py

def make_env_pre_post_processors(env_cfg: EnvConfig):
    if isinstance(env_cfg, LiberoEnv) or "libero" in env_cfg.type:
        preprocessor = PolicyProcessorPipeline(steps=[LiberoProcessorStep()])
    elif isinstance(env_cfg, MyEnvConfig) or "myenv" in env_cfg.type:
        preprocessor = PolicyProcessorPipeline(steps=[MyEnvProcessorStep()])
    else:
        preprocessor = PolicyProcessorPipeline(steps=[])

    postprocessor = PolicyProcessorPipeline(steps=[])
    return preprocessor, postprocessor
```

### 3. 在评估中使用

无需更改！评估脚本会自动使用适当的处理器。

```
lerobot-eval \
    --policy.path=lerobot/my_policy \
    --env.type=myenv \  # Automatically uses MyEnvProcessorStep
    --eval.n_episodes=10
```

## 未来展望：环境后处理器

目前，所有环境的后处理器均为空操作（no-op）。未来的用例包括：

### 动作空间转换

```
@dataclass
class MyEnvActionPostprocessor(ProcessorStep):
    """Convert policy actions to environment-specific format."""

    def __call__(self, transition: EnvTransition) -> EnvTransition:
        action = transition["action"]

        # Example: Convert from Cartesian to joint space
        if self.action_space == "joint":
            action = self.ik_solver(action)

        # Example: Apply environment-specific safety limits
        action = torch.clamp(action, self.min_action, self.max_action)

        transition["action"] = action
        return transition
```

### 坐标系转换

```
@dataclass
class CoordinateTransformPostprocessor(ProcessorStep):
    """Transform actions between coordinate systems."""

    def __call__(self, transition: EnvTransition) -> EnvTransition:
        action = transition["action"]

        # Example: Policy outputs in world frame, env expects base frame
        action = self.world_to_base_transform(action)

        transition["action"] = action
        return transition
```

## 最佳实践

1. **保持环境处理器简单**：它们应该只处理特定于环境的数据格式问题，而不是复杂的学习相关转换。
2. **使用策略处理器处理模型需求**：归一化、批处理、设备放置和分词化应属于策略处理器。
3. **从环境公开所有数据**：让处理器决定使用什么，而不是在环境中硬编码选择。
4. **记录规范**：清晰地记录您的处理器所处理的任何坐标系规范、相机朝向或数据格式。
5. **独立测试**：环境处理器应能够在不加载完整策略或环境的情况下进行测试。

## 总结

环境处理器在特定于环境的数据转换和特定于策略的模型需求之间提供了**清晰的分离**。该架构：

* ✅ 能够轻松试验不同的状态表示
* ✅ 允许策略在不同环境中无缝工作
* ✅ 使环境代码专注于模拟/硬件接口
* ✅ 使处理器流水线更易于维护和调试
* ✅ 遵循单一职责原则

关键洞察：**环境定义数据格式，处理器对其进行标准化，策略使用标准化的数据。**每一层都有明确、专注的职责。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/env_processor.mdx)
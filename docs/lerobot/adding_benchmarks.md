# 来源

https://hugging-face.cn/docs/lerobot/adding_benchmarks

# 添加新基准

本指南将引导您向 LeRobot 添加新的模拟基准。请按顺序执行这些步骤，并使用现有的基准作为模板。

LeRobot 中的基准是一组 [Gymnasium](https://gymnasium.org.cn/) 环境，它们在标准的 `gym.Env` 接口背后封装了第三方模拟器（如 LIBERO 或 Meta-World）。然后，`lerobot-eval` CLI 会在所有基准上统一运行评估。

## 现有基准一览

在深入了解之前，以下是已经集成的内容

| 基准测试 | 环境文件 | 配置类 | 任务 | 动作维度 | 处理器 |
| --- | --- | --- | --- | --- | --- |
| LIBERO | `envs/libero.py` | `LiberoEnv` | 跨 5 个套件共 130 个 | 7 | `LiberoProcessorStep` |
| Meta-World | `envs/metaworld.py` | `MetaworldEnv` | 50 (MT50) | 4 | 无 |
| IsaacLab Arena | 托管于 Hub | `IsaaclabArenaEnv` | 可配置 | 可配置 | `IsaaclabArenaProcessorStep` |

请使用 `src/lerobot/envs/libero.py` 和 `src/lerobot/envs/metaworld.py` 作为参考实现。

## 各部分如何协同工作

### 数据流

在评估期间，数据会经历四个阶段

```
1. gym.Env  ──→  raw observations (numpy dicts)

2. Preprocessing  ──→  standard LeRobot keys + task description
   (preprocess_observation, add_envs_task in envs/utils.py)

3. Processors  ──→  env-specific then policy-specific transforms
   (env_preprocessor, policy_preprocessor)

4. Policy  ──→  select_action()  ──→  action tensor
   then reverse: policy_postprocessor → env_postprocessor → numpy action → env.step()
```

大多数基准只需要关心阶段 1（以正确的格式生成观测值）以及可选的阶段 3（如果需要特定于环境的转换）。

### 环境结构

`make_env()` 返回一个矢量化环境的嵌套字典

```
dict[str, dict[int, gym.vector.VectorEnv]]
#    ^suite       ^task_id
```

单任务环境（例如 PushT）看起来像 `{"pusht": {0: vec_env}}`。多任务基准（例如 LIBERO）看起来像 `{"libero_spatial": {0: vec0, 1: vec1, ...}, ...}`。

### 评估如何运行

所有基准都由 `lerobot-eval` 以相同的方式进行评估

1. `make_env()` 构建嵌套的 `{suite: {task_id: VectorEnv}}` 字典。
2. `eval_policy_all()` 迭代每个套件和任务。
3. 对于每个任务，它通过 `rollout()` 运行 `n_episodes` 次展开（rollout）。
4. 结果按层级进行汇总：回合（episode）、任务（task）、套件（suite）、整体（overall）。
5. 指标包括 `pc_success`（成功率）、`avg_sum_reward` 和 `avg_max_reward`。

关键点：您的环境必须在每次调用 `step()` 时返回 `info["is_success"]`。这就是评估循环如何得知任务是否完成的方式。

## 您的环境必须提供什么

LeRobot 并不强制执行严格的观测模式（schema）。相反，它依赖于所有基准都遵循的一套约定。

### 环境属性

您的 `gym.Env` 必须设置这些属性

| 属性 | 类型 | 原因 |
| --- | --- | --- |
| `_max_episode_steps` | `int` | `rollout()` 使用此属性来限制回合长度上限 |
| `task_description` | `字符串` | 作为语言指令传递给 VLA 策略 |
| `任务` | `字符串` | 如果未设置 `task_description` 时的后备标识符 |

### 成功报告

您的 `step()` 和 `reset()` 必须在 `info` 字典中包含 `"is_success"`

```
info = {"is_success": True}   # or False
return observation, reward, terminated, truncated, info
```

### 观测信息

最简单的方法是将模拟器的输出映射到 `preprocess_observation()` 已经能够理解的标准键上。在您的 `gym.Env` 内部执行此操作（例如在 `_format_raw_obs()` 辅助函数中）

| 您的环境应该输出 | LeRobot 将其映射为 | 它的含义 |
| --- | --- | --- |
| `"pixels"`（单个数组） | `observation.image` | 单相机图像，HWC uint8 |
| `"pixels"`（字典） | `observation.images.<cam>` | 多相机，每个均为 HWC uint8 |
| `"agent_pos"` | `observation.state` | 本体感受状态向量 |
| `"environment_state"` | `observation.env_state` | 完整环境状态（例如 PushT） |
| `"robot_state"` | `observation.robot_state` | 嵌套的机器人状态字典（例如 LIBERO） |

如果您的模拟器使用不同的键名，您有两个选择

1. **推荐：** 在您的 `gym.Env` 封装器内部将它们重命名为标准键。
2. **备选方案：** 编写一个环境处理器，在 `preprocess_observation()` 运行后对观测值进行转换（参见下面的步骤 4）。

### 动作 (Actions)

动作是 `gym.spaces.Box` 中的连续 numpy 数组。维度取决于您的基准（LIBERO 为 7，Meta-World 为 4，等等）。策略通过其 `input_features` / `output_features` 配置来适应不同的动作维度。

### 特征声明

每个 `EnvConfig` 子类都会声明两个字典，以告知策略预期的内容

* `features` — 将特征名称映射到 `PolicyFeature(type, shape)`（例如动作维度、图像形状）。
* `features_map` — 将原始观测键映射到 LeRobot 约定键（例如将 `"agent_pos"` 映射到 `"observation.state"`）。

## 分步指南

> 最少情况下，您需要三个文件：一个 \*\*gym.Env 封装器\*\*、一个 \*\*EnvConfig 子类\*\* 以及一个 \*\*工厂调度分支\*\*。其他所有内容都是可选的或属于文档。

### 清单

| 文件 | 必需 | 原因 |
| --- | --- | --- |
| `src/lerobot/envs/<benchmark>.py` | 是 | 将模拟器封装为标准 gym.Env |
| `src/lerobot/envs/configs.py` | 是 | 为 CLI 注册您的基准 |
| `src/lerobot/envs/factory.py` | 是 | 告诉 `make_env()` 如何构建您的环境 |
| `src/lerobot/processor/env_processor.py` | 可选 | 自定义观测/动作转换 |
| `src/lerobot/envs/utils.py` | 可选 | 仅当您需要新的原始观测键时才需要 |
| `pyproject.toml` | 是 | 声明基准特定的依赖项 |
| `docs/source/<benchmark>.mdx` | 是 | 面向用户的文档页面 |
| `docs/source/_toctree.yml` | 是 | 将您的页面添加到文档侧边栏 |

### 1. gym.Env 封装器 ( src/lerobot/envs/<benchmark>.py )

创建一个封装第三方模拟器的 `gym.Env` 子类

```
class MyBenchmarkEnv(gym.Env):
    metadata = {"render_modes": ["rgb_array"], "render_fps": <fps>}

    def __init__(self, task_suite, task_id, ...):
        super().__init__()
        self.task = <task_name_string>
        self.task_description = <natural_language_instruction>
        self._max_episode_steps = <max_steps>
        self.observation_space = spaces.Dict({...})
        self.action_space = spaces.Box(low=..., high=..., shape=(...,), dtype=np.float32)

    def reset(self, seed=None, **kwargs):
        ...  # return (observation, info) — info must contain {"is_success": False}

    def step(self, action: np.ndarray):
        ...  # return (obs, reward, terminated, truncated, info) — info must contain {"is_success": <bool>}

    def render(self):
        ...  # return RGB image as numpy array

    def close(self):
        ...
```

同时提供一个返回嵌套字典结构的工厂函数

```
def create_mybenchmark_envs(
    task: str,
    n_envs: int,
    gym_kwargs: dict | None = None,
    env_cls: type | None = None,
) -> dict[str, dict[int, Any]]:
    """Create {suite_name: {task_id: VectorEnv}} for MyBenchmark."""
    ...
```

请参考 `create_libero_envs()`（多套件、多任务）和 `create_metaworld_envs()`（按难度分组的任务）。

### 2. 配置 ( src/lerobot/envs/configs.py )

注册一个配置数据类，以便用户可以通过 `--env.type=<name>` 选择您的基准

```
@EnvConfig.register_subclass("<benchmark_name>")
@dataclass
class MyBenchmarkEnvConfig(EnvConfig):
    task: str = "<default_task>"
    fps: int = <fps>
    obs_type: str = "pixels_agent_pos"

    features: dict[str, PolicyFeature] = field(default_factory=lambda: {
        ACTION: PolicyFeature(type=FeatureType.ACTION, shape=(<action_dim>,)),
    })
    features_map: dict[str, str] = field(default_factory=lambda: {
        ACTION: ACTION,
        "agent_pos": OBS_STATE,
        "pixels": OBS_IMAGE,
    })

    def __post_init__(self):
        ...  # populate features based on obs_type

    @property
    def gym_kwargs(self) -> dict:
        return {"obs_type": self.obs_type, "render_mode": self.render_mode}
```

关键点

* `register_subclass` 名称是用户在 CLI 上传递的值（`--env.type=<name>`）。
* `features` 告诉策略环境产生什么。
* `features_map` 将原始观测键映射到 LeRobot 约定键。

### 3. 工厂调度 ( src/lerobot/envs/factory.py )

在 `make_env()` 中添加一个分支以调用您的工厂函数

```
elif "<benchmark_name>" in cfg.type:
    from lerobot.envs.<benchmark> import create_<benchmark>_envs

    if cfg.task is None:
        raise ValueError("<BenchmarkName> requires a task to be specified")

    return create_<benchmark>_envs(
        task=cfg.task,
        n_envs=n_envs,
        gym_kwargs=cfg.gym_kwargs,
        env_cls=env_cls,
    )
```

如果您的基准需要环境处理器，请在 `make_env_pre_post_processors()` 中添加它

```
if isinstance(env_cfg, MyBenchmarkEnvConfig) or "<benchmark_name>" in env_cfg.type:
    preprocessor_steps.append(MyBenchmarkProcessorStep())
```

### 4. 环境处理器（可选 — src/lerobot/processor/env\_processor.py ）

仅在您的基准需要超出 `preprocess_observation()` 处理范围的观测转换时才需要（例如图像翻转、坐标转换）

```
@dataclass
@ProcessorStepRegistry.register(name="<benchmark>_processor")
class MyBenchmarkProcessorStep(ObservationProcessorStep):
    def _process_observation(self, observation):
        processed = observation.copy()
        # your transforms here
        return processed

    def transform_features(self, features):
        return features  # update if shapes change

    def observation(self, observation):
        return self._process_observation(observation)
```

请参见 `LiberoProcessorStep` 以获取完整示例（图像旋转、四元数到轴角转换）。

### 5. 依赖项 ( pyproject.toml )

添加一个新的可选依赖项组

```
mybenchmark = ["my-benchmark-pkg==1.2.3", "lerobot[scipy-dep]"]
```

版本固定规则

* **务必固定**基准软件包的精确版本以确保可复现性（例如 `metaworld==3.0.0`）。
* 必要时**添加平台标记**（例如 `; sys_platform == 'linux'`）。
* 如果已知，**固定脆弱的传递依赖项**（例如 Meta-World 依赖的 `gymnasium==1.1.0`）。
* 在您的基准文档页面中**说明限制条件**。

用户使用以下命令安装

```
pip install -e ".[mybenchmark]"
```

### 6. 文档 ( docs/source/<benchmark>.mdx )

按照下一节中的模板编写一个面向用户的页面。请参见 `docs/source/libero.mdx` and `docs/source/metaworld.mdx` 获取完整示例。

### 7. 目录 ( docs/source/\_toctree.yml )

将您的基准添加到 “Benchmarks” 部分

```
- sections:
    - local: libero
      title: LIBERO
    - local: metaworld
      title: Meta-World
    - local: envhub_isaaclab_arena
      title: NVIDIA IsaacLab Arena Environments
    - local: <your_benchmark>
      title: <Your Benchmark Name>
  title: "Benchmarks"
```

## 验证您的集成

完成上述步骤后，确认一切运行正常

1. **安装** — 运行 `pip install -e ".[mybenchmark]"` 并验证依赖项组是否可以干净地安装。
2. **冒烟测试环境创建** — 在 Python 中使用您的配置调用 `make_env()`，检查返回的字典是否具有预期的 `{suite: {task_id: VectorEnv}}` 结构，以及 `reset()` 返回的观测值是否具有正确的键。
3. **运行完整评估** — 运行 `lerobot-eval --env.type=<name> --env.task=<task> --eval.n_episodes=1 --eval.batch_size=1 --policy.path=<any_compatible_policy>` 以端到端运行整个流水线。
4. **检查成功检测** — 验证当任务实际完成时 `info["is_success"]` 是否翻转为 `True`。这是评估循环用来计算成功率的依据。

## 撰写基准文档页面

每个基准的 `.mdx` 页面应包含

* **标题和描述** — 用 1-2 段文字说明该基准测试什么以及为什么它很重要。
* **链接** — 论文、GitHub 仓库、项目网站（如果有）。
* **概览图片或 GIF。**
* **可用任务** — 任务套件的表格，包含数量和简要描述。
* **安装** — `pip install -e ".[<benchmark>]"` 以及任何额外步骤（环境变量、系统软件包）。
* **评估** — 推荐使用带有 `n_episodes` 和 `batch_size` 的 `lerobot-eval` 命令以获得可复现的结果。如果适用，请包括单任务和多任务示例。
* **策略输入和输出** — 包含形状的观测键、动作空间描述。
* **推荐的评估回合数** — 每个任务的标准回合数是多少。
* **训练** — `lerobot-train` 命令示例。
* **复现已发表的结果** — 预训练模型的链接、评估命令、结果表格（如果有）。

参见 `docs/source/libero.mdx` 和 `docs/source/metaworld.mdx` 获取完整示例。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/adding_benchmarks.mdx)
# 来源

https://hugging-face.cn/docs/lerobot/envhub

# 从 Hub 加载环境

**EnvHub** 功能允许您仅用一行代码直接从 Hugging Face Hub 加载仿真环境。这开启了一种强大的协作新模式：环境不再被锁定在庞大的单一库中，任何人都可以发布自定义环境并将其分享给社区。

## 什么是 EnvHub？

EnvHub 让您可以使用自己的机器人模型和场景创建自定义机器人仿真环境，并通过 LeRobot 框架使其能够被任何人轻松使用。

EnvHub 包存储在 Hugging Face Hub 上，并且可以通过 LeRobot 仅用一行代码无缝集成到您的 AI 机器人项目中。

得益于 EnvHub，您可以：

1. **创建并发布环境**到 Hugging Face Hub 作为 Git 仓库，分发复杂的物理模拟而无须面对打包困扰
2. **动态加载环境**，无须将它们安装为包
3. 使用 Git 语义对环境更改进行**版本控制和跟踪**
4. **发现**由社区分享的新仿真任务

这种设计意味着您可以几秒钟内完成从 Hub 发现有趣环境到运行实验的过程，或者创建自己的自定义机器人和环境，而无须担心依赖冲突或复杂的安装程序。

当您创建一个 EnvHub 包时，您可以在其中构建任何您想要的内容，并使用您喜欢的任何仿真工具：这是您自己的游玩空间。唯一的要求是该包包含一个 `env.py` 文件，用于定义环境并允许 LeRobot 加载及使用您的 EnvHub 包。

这个 `env.py` 文件需要暴露一小部分 API 以便 LeRobot 加载和运行。特别地，您必须提供一个 `make_env(n_envs: int = 1, use_async_envs: bool = False)` 或 `make_env(n_envs: int = 1, use_async_envs: bool = False, cfg: EnvConfig)` 函数，它是 LeRobot 的主要入口点。它应该返回以下内容之一：

* 一个 `gym.vector.VectorEnv` (最常见)
* 单个 `gym.Env` (将被自动包装)
* 一个字典映射 `{suite_name: {task_id: VectorEnv}}` (用于多任务基准测试)

您还可以将 `EnvConfig` 对象传递给 `make_env` 以配置环境（例如环境数量、任务、摄像头名称、初始状态、控制模式、回合长度等）。

最后，您的环境必须实现标准的 `gym.vector.VectorEnv` 接口，以便它可以与 LeRobot 配合使用，包括 `reset` 和 `step` 等方法。

## 快速开始

从 Hub 加载环境就像这样简单：

```
from lerobot.envs.factory import make_env

# Load a hub environment (requires explicit consent to run remote code)
env = make_env("lerobot/cartpole-env", trust_remote_code=True)
```

> \*\*安全须知\*\*：从 Hub 加载环境会执行来自第三方仓库的 Python 代码。仅对您信任的仓库使用 `trust\_remote\_code=True`。我们强烈建议锁定到特定的提交哈希以确保可复现性和安全性。

## 仓库结构

为了使您的环境能够从 Hub 加载，您的仓库至少必须包含：

### 必要文件

**`env.py`** (或自定义 Python 文件)

* 必须暴露一个 `make_env(n_envs: int, use_async_envs: bool)` 函数
* 此函数应返回以下内容之一：
  + 一个 `gym.vector.VectorEnv` (最常见)
  + 单个 `gym.Env` (将被自动包装)
  + 一个字典映射 `{suite_name: {task_id: VectorEnv}}` (用于多任务基准测试)

### 可选文件

**`requirements.txt`**

* 列出您的环境所需的任何附加依赖项
* 用户在加载您的环境之前需要手动安装这些依赖

**`README.md`**

* 记录您的环境：它实现了什么任务、观测/动作空间、奖励等。
* 包含用法示例和任何特殊的设置说明

**`.gitignore`**

* 从您的仓库中排除不必要的文件

### 示例仓库结构

```
my-environment-repo/
├── env.py                 # Main environment definition (required)
├── requirements.txt       # Dependencies (optional)
├── README.md             # Documentation (recommended)
├── assets/               # Images, videos, etc. (optional)
│   └── demo.gif
└── configs/              # Config files if needed (optional)
    └── task_config.yaml
```

## 创建您的环境仓库

### 第一步：定义您的环境

创建一个带有 `make_env` 函数的 `env.py` 文件

```
# env.py
import gymnasium as gym

def make_env(n_envs: int = 1, use_async_envs: bool = False):
    """
    Create vectorized environments for your custom task.

    Args:
        n_envs: Number of parallel environments
        use_async_envs: Whether to use AsyncVectorEnv or SyncVectorEnv

    Returns:
        gym.vector.VectorEnv or dict mapping suite names to vectorized envs
    """
    def _make_single_env():
        # Create your custom environment
        return gym.make("CartPole-v1")

    # Choose vector environment type
    env_cls = gym.vector.AsyncVectorEnv if use_async_envs else gym.vector.SyncVectorEnv

    # Create vectorized environment
    vec_env = env_cls([_make_single_env for _ in range(n_envs)])

    return vec_env
```

### 第二步：本地测试

在上传之前，请在本地测试您的环境

```
from lerobot.envs.utils import _load_module_from_path, _call_make_env, _normalize_hub_result

# Load your module
module = _load_module_from_path("./env.py")

# Test the make_env function
result = _call_make_env(module, n_envs=2, use_async_envs=False)
normalized = _normalize_hub_result(result)

# Verify it works
suite_name = next(iter(normalized))
env = normalized[suite_name][0]
obs, info = env.reset()
print(f"Observation shape: {obs.shape if hasattr(obs, 'shape') else type(obs)}")
env.close()
```

### 第三步：上传到 Hub

将您的仓库上传到 Hugging Face

```
# Install huggingface_hub if needed
pip install huggingface_hub

# Login to Hugging Face
hf auth login

# Create a new repository
hf repo create my-org/my-custom-env

# Initialize git and push
git init
git add .
git commit -m "Initial environment implementation"
git remote add origin https://hugging-face.cn/my-org/my-custom-env
git push -u origin main
```

或者，使用 `huggingface_hub` Python API

```
from huggingface_hub import HfApi

api = HfApi()

# Create repository
api.create_repo("my-custom-env", repo_type="space")

# Upload files
api.upload_folder(
    folder_path="./my-env-folder",
    repo_id="username/my-custom-env",
    repo_type="space",
)
```

## 从 Hub 加载环境

### 基本用法

```
from lerobot.envs.factory import make_env

# Load from the hub
envs_dict = make_env(
    "username/my-custom-env",
    n_envs=4,
    trust_remote_code=True
)

# Access the environment
suite_name = next(iter(envs_dict))
env = envs_dict[suite_name][0]

# Use it like any gym environment
obs, info = env.reset()
action = env.action_space.sample()
obs, reward, terminated, truncated, info = env.step(action)
```

### 进阶：锁定到特定版本

为了可复现性和安全性，请锁定到特定的 Git revision

```
# Pin to a specific branch
env = make_env("username/my-env@main", trust_remote_code=True)

# Pin to a specific commit (recommended for papers/experiments)
env = make_env("username/my-env@abc123def456", trust_remote_code=True)

# Pin to a tag
env = make_env("username/my-env@v1.0.0", trust_remote_code=True)
```

### 自定义文件路径

如果您的环境定义不在 `env.py` 中

```
# Load from a custom file
env = make_env("username/my-env:custom_env.py", trust_remote_code=True)

# Combine with version pinning
env = make_env("username/my-env@v1.0:envs/task_a.py", trust_remote_code=True)
```

### 异步环境

为了在多个环境运行时获得更好的性能

```
envs_dict = make_env(
    "username/my-env",
    n_envs=8,
    use_async_envs=True,  # Use AsyncVectorEnv for parallel execution
    trust_remote_code=True
)
```

## URL 格式参考

hub URL 格式支持几种模式

| 模式 | 描述 | 示例 |
| --- | --- | --- |
| `user/repo` | 从 main 分支加载 `env.py` | `make_env("lerobot/pusht-env")` |
| `user/repo@revision` | 从特定 revision 加载 | `make_env("lerobot/pusht-env@main")` |
| `user/repo:path` | 加载自定义文件 | `make_env("lerobot/envs:pusht.py")` |
| `user/repo@rev:path` | Revision + 自定义文件 | `make_env("lerobot/envs@v1:pusht.py")` |

## 多任务环境

对于包含多个任务的基准测试（如 LIBERO），请返回一个嵌套字典

```
def make_env(n_envs: int = 1, use_async_envs: bool = False):
    env_cls = gym.vector.AsyncVectorEnv if use_async_envs else gym.vector.SyncVectorEnv

    # Return dict: {suite_name: {task_id: VectorEnv}}
    return {
        "suite_1": {
            0: env_cls([lambda: gym.make("Task1-v0") for _ in range(n_envs)]),
            1: env_cls([lambda: gym.make("Task2-v0") for _ in range(n_envs)]),
        },
        "suite_2": {
            0: env_cls([lambda: gym.make("Task3-v0") for _ in range(n_envs)]),
        }
    }
```

## 安全注意事项

> \*\*重要\*\*：必须设置 `trust\_remote\_code=True` 标志才能执行来自 Hub 的环境代码。这是出于安全设计的考虑。

从 Hub 加载环境时：

1. **先审查代码**：加载前先访问仓库并检查 `env.py`
2. **锁定到 commit**：使用特定的提交哈希以确保可复现性
3. **检查依赖项**：审查 `requirements.txt` 以排除可疑包
4. **使用可信来源**：优先选择官方组织或知名研究人员
5. **必要时进行沙盒化**：在隔离环境（容器、虚拟机）中运行不受信任的代码

安全使用的示例

```
# ❌ BAD: Loading without inspection
env = make_env("random-user/untrusted-env", trust_remote_code=True)

# ✅ GOOD: Review code, then pin to specific commit
# 1. Visit https://hugging-face.cn/trusted-org/verified-env
# 2. Review the env.py file
# 3. Copy the commit hash
env = make_env("trusted-org/verified-env@a1b2c3d4", trust_remote_code=True)
```

## 示例：来自 Hub 的 CartPole

这是一个使用参考版 CartPole 环境的完整示例

```
from lerobot.envs.factory import make_env
import numpy as np

# Load the environment
envs_dict = make_env("lerobot/cartpole-env", n_envs=4, trust_remote_code=True)

# Get the vectorized environment
suite_name = next(iter(envs_dict))
env = envs_dict[suite_name][0]

# Run a simple episode
obs, info = env.reset()
done = np.zeros(env.num_envs, dtype=bool)
total_reward = np.zeros(env.num_envs)

while not done.all():
    # Random policy
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    total_reward += reward
    done = terminated | truncated

print(f"Average reward: {total_reward.mean():.2f}")
env.close()
```

## EnvHub 的优势

### 对于环境作者

* **易于分发**：无须 PyPI 打包
* **版本控制**：使用 Git 进行环境版本管理
* **快速迭代**：即时推送更新
* **文档**：Hub README 渲染精美
* **社区**：直接触达 LeRobot 用户

### 对于研究人员

* **快速实验**：一行代码加载任何环境
* **可复现性**：锁定到特定 commit
* **发现**：在 Hub 上浏览环境
* **无冲突**：无须安装冲突的包

### 对于社区

* **不断壮大的生态系统**：更多样化的仿真任务
* **标准化**：统一的 `make_env` API
* **协作**：Fork 并改进现有环境
* **可及性**：降低分享研究成果的门槛

## 疑难解答

### “拒绝执行远程代码”

您必须显式传递 `trust_remote_code=True`

```
env = make_env("user/repo", trust_remote_code=True)
```

### “Module X not found”

Hub 环境有需要您安装的依赖项

```
# Check the repo's requirements.txt and install dependencies
pip install gymnasium numpy
```

### “make\_env not found in module”

您的 `env.py` 必须暴露一个 `make_env` 函数

```
def make_env(n_envs: int, use_async_envs: bool):
    # Your implementation
    pass
```

### 环境返回类型错误

`make_env` 函数必须返回：

* 一个 `gym.vector.VectorEnv`，或者
* 单个 `gym.Env`，或者
* 一个字典 `{suite_name: {task_id: VectorEnv}}`

## 最佳实践

1. **记录您的环境**：在 README 中包含观测/动作空间说明、奖励结构和终止条件
2. **添加 requirements.txt**：列出所有带有版本的依赖项
3. **彻底测试**：在推送前验证您的环境在本地工作正常
4. **使用语义化版本控制**：使用版本号标记 release
5. **添加示例**：在 README 中包含用法示例
6. **保持简洁**：尽可能减少依赖项
7. **授权您的作品**：添加 LICENSE 文件以明确使用条款

## 未来方向

EnvHub 生态系统带来了令人兴奋的可能性：

* **GPU 加速物理模拟**：分享 Isaac Gym 或 Brax 环境
* **照片级渲染**：分发带有高级图形效果的环境
* **多智能体场景**：复杂的交互任务
* **现实世界模拟器**：物理装置的数字孪生
* **程序化生成**：无限的任务变体
* **领域随机化**：预配置的 DR 流水线

随着更多研究人员和开发者的贡献，可用环境的多样性和质量将不断提高，从而使整个机器人学习社区受益。

## 参见

* [Hugging Face Hub 文档](https://hugging-face.cn/docs/hub/en/index)
* [Gymnasium 文档](https://gymnasium.org.cn/index.html)
* [Hub 环境示例](https://hugging-face.cn/lerobot/cartpole-env)

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/envhub.mdx)
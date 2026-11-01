# core

Python 3.11+ 核心，基础层使用标准库，机器人学习使用 LeRobot，物理仿真使用 MuJoCo。具体设备和算法通过类接口接入。

| 模块 | 职责 |
| --- | --- |
| `collection` | 单帧采集与 JSONL episode 记录，已有文件不会覆盖 |
| `communication` | 设备连接、观测读取、动作发送的抽象接口 |
| `training` | 训练配置、结果和算法适配接口 |
| `inference` | 策略加载、状态重置、观测到动作的推理接口 |
| `integrations` | LeRobot 原生数据集创建与读取入口 |
| `simulation` | MuJoCo URDF 加载、状态读取、位置目标和显式物理步进 |
| `llm` | OpenAI SDK 封装、模型配置、文本生成与 token 用量 |
| `agent` | SQLite 会话历史、SKILL.md 加载、流式对话和命令行入口 |
| `contracts.py` | 共享观测、动作类型，关节位置单位为弧度 |

复用本机已有 Conda `base` 环境，不创建独立环境。运行依赖包含 `lerobot==0.4.4`、`mujoco==3.15.0`、`openai==2.24.0`、`PyYAML>=6.0.2,<7`，记录在 `pyproject.toml`。在本目录执行：

```powershell
conda activate base
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
```

以上 `PYTHONPATH` 仅对当前 PowerShell 会话生效，之后可直接导入 `xiaoxia_core`。`pyproject.toml` 保留包元数据，后续运行依赖统一记录在其中，使用 Conda 管理已有 `base` 环境。

### PyTorch GPU 依赖

当前 Windows 主机使用 Python 3.13、RTX 4060 和 NVIDIA 驱动 566.24。与 LeRobot 0.4.4 的依赖范围匹配的 GPU 组合为 `torch==2.10.0`、`torchvision==0.25.0`、`torchaudio==2.10.0`，使用 CUDA 12.6 预编译包。需要重装时在已有 `base` 环境执行：

```powershell
conda activate base
python -m pip install torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu126
```

不创建新环境、不从源码编译 PyTorch。安装源参考 [PyTorch 官方版本说明](https://pytorch.org/get-started/previous-versions/)。

2026-11-01 已在现有 `base` 安装上述三件套（版本后缀 `+cu126`），最小导入和 `torch.cuda.is_available()` 检查通过，识别 RTX 4060 Laptop GPU。SymPy 随之更新到 1.14.0；未运行训练或性能测试。

共享 `base` 尚非全部依赖兼容：本次升级超出 `lightx2v==0.1.0` 对 torch/torchaudio≤2.8.0、torchvision≤0.23.0 的声明范围，LightX2V 运行未验收。原有 LeRobot 与 `diffusers==0.38.0.dev0`（要求 <0.36.0）、OSAM 与 `onnxruntime==1.20.1` 的依赖冲突也尚未处理，不能据此认为完整 LeRobot 训练已可运行。

## 库入口

```python
from pathlib import Path
from xiaoxia_core.integrations import LeRobotDatasets
from xiaoxia_core.simulation import MujocoSimulation, SimulationConfig

# 在 core 目录运行，复用 table 中已有的模型及网格。
urdf = Path('../table/public/robots/so101/so101_new_calib.urdf')
with MujocoSimulation(SimulationConfig(urdf_path=urdf)) as simulation:
    observation = simulation.read_observation()
    observation = simulation.step()

# 读取已有本地 LeRobot 数据集，不下载视频。
# dataset = LeRobotDatasets.open('local/so101', Path('data/so101'))
```

`MujocoSimulation` 实现 `RobotTransport`，可直接传给 `CollectionService`。`send_action` 仅更新目标，`step` 才推进物理时间；观测时间戳来自仿真时间，与实机时钟不同。默认固定步长 0.002 秒，重力采用 MuJoCo 默认值，底座固定。

位置控制使用有力矩上限的 PD 控制器；默认增益和力矩上限仅为可调整的仿真参数，未经实机标定。网格碰撞由 MuJoCo 导入处理，尚未验收自碰撞、接触精度和控制稳定性。模块不自动打开渲染窗口、不驱动物理设备。

`LeRobotDatasets.create` 返回原生 `LeRobotDataset`，由调用方使用 `add_frame`、`save_episode` 写入数据。已有 JSONL 记录器不等同于 LeRobot 数据集，尚无格式转换器。训练可使用 LeRobot 自带的 `lerobot-train` 入口；当前核心尚未封装具体策略训练与推理。

调用方用上下文管理器管理 `RobotTransport` 和 `EpisodeRecorder`，再将它们传给 `CollectionService`。采集节拍由调用方决定；图像记录为路径，图像文件由数据源保存。

尚未实现 SO-ARM-101 串口协议、摄像头、具体训练算法、推理模型和桌面 IPC。训练和推理必须注入真实适配器；推理只返回动作，不自动发送到设备。

## LLM

`llm` 使用 OpenAI Responses API，调用方必须指定自己有权限使用的模型。PowerShell 中先设置 `OPENAI_API_KEY` 和 `OPENAI_MODEL`；可选 `OPENAI_BASE_URL` 必须指向支持 Responses API 的地址。`.env.example` 仅列出变量，模块不自动加载 `.env`。

```python
from xiaoxia_core.llm import LLMConfig, OpenAILLM

with OpenAILLM(LLMConfig.from_env()) as llm:
    result = llm.generate('解释机械臂关节位置与末端位置的区别。', instructions='用简体中文回答。')
    print(result.text)
```

仅调用 `generate` 时发送请求；结果包含文本、响应 ID、实际模型与 token 用量。默认请求超时 60 秒、SDK 最多重试 2 次、输出上限 2048 token、`store=False`。API 异常直接交给调用方处理，未完成响应和空文本会显式报错。LLM 不直接控制机械臂。代码未进行真实 API 调用验证。

接口依据 [OpenAI Python SDK 官方文档](https://developers.openai.com/api/reference/python)。

## 简单 Agent

激活 `base`，在 `core` 目录设置当前会话的环境变量后启动：

```powershell
conda activate base
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
$env:OPENAI_API_KEY = '你的密钥'
$env:OPENAI_MODEL = '你有访问权限的模型名称'
python -m xiaoxia_core.agent
```

默认会话保存在 `core/data/agent.sqlite3`（已忽略提交），默认技能目录为 `core/skills`。可通过 `--database 路径`、`--skills 路径`、`--session 会话ID` 指定位置或恢复会话。命令行直接显示流式文本；`Ctrl+C` 中断当前轮，输入阶段按 `Ctrl+C` 或 `/quit` 退出。

| 命令 | 功能 |
| --- | --- |
| `/new` | 创建并切换会话 |
| `/sessions`、`/resume ID` | 列出、恢复会话 |
| `/history`、`/clear` | 查看、清空当前会话消息 |
| `/skills` | 刷新并列出技能 |
| `/skill robotics-guide` | 启用技能，空格分隔可选多个 |
| `/skill off` | 关闭当前技能 |

技能目录格式为 `<技能目录>/<名称>/SKILL.md`，YAML frontmatter 必须提供 `name`、`description`，正文是技能指令。名称使用小写字母数字及连字符。技能由调用方显式选择，不自动执行其中的脚本；当前会话切换不改变 CLI 已选技能，重启后需重新选择。

`SimpleAgent.stream(session_id, text, skill_names=...)` 返回 `started`、`skill_loaded`、`delta`、`completed` 事件。`completed.result` 包含最终文本与用量。`agent.bridge` 已为 `table` 提供单请求 JSONL 桥接，支持 bootstrap/create/history/clear/run；由 Tauri 子进程调用，不开启 HTTP 监听，运行目录必须为 `core`。

```python
from contextlib import closing
from pathlib import Path
from xiaoxia_core.agent import SessionStore, SimpleAgent, SkillRegistry
from xiaoxia_core.llm import LLMConfig, OpenAILLM

sessions = SessionStore(Path('data/agent.sqlite3'))
session_id = sessions.create()
with OpenAILLM(LLMConfig.from_env()) as llm:
    agent = SimpleAgent(llm, sessions, SkillRegistry(Path('skills')))
    with closing(agent.stream(session_id, '如何准备机械臂采集数据？',
                              skill_names=['robotics-guide'])) as events:
        for event in events:
            if event.type == 'delta':
                print(event.delta, end='', flush=True)
```

每轮发送最近 20 轮完整历史（可配置，按轮数而非 token 裁剪）。仅在完整响应成功后原子保存 user/assistant 两条消息；流异常、未完成、主动关闭或生成期间会话版本冲突都不会写入本轮。异常由调用方捕获，提前结束消费时需像示例一样关闭迭代器。中途显示的文本是预览，`completed` 才表示已保存。

这是文本对话 Agent，不含工具调用循环、自动选择技能、长上下文摘要、异步并发或硬件执行。流式接口依据 [OpenAI 流式响应文档](https://developers.openai.com/api/docs/guides/streaming-responses)。未发送实际 API 请求，尚未验收联网交互。

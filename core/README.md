# core

Python 3.11+ 核心，基础层使用标准库，机器人学习使用 LeRobot，物理仿真使用 MuJoCo。具体设备和算法通过类接口接入。

| 模块 | 职责 |
| --- | --- |
| `collection` | 单帧采集与 JSONL episode 记录，已有文件不会覆盖 |
| `communication` | SO-100/101 共用 Feetech 通信、只读连接和显式使能 |
| `training` | 训练配置、结果和算法适配接口 |
| `inference` | 策略加载、状态重置、观测到动作的推理接口 |
| `integrations` | LeRobot 原生数据集创建与读取入口 |
| `simulation` | MuJoCo URDF 加载、状态读取、位置目标和显式物理步进 |
| `llm` | OpenAI SDK 封装、模型配置、文本生成与 token 用量 |
| `agent` | SQLite 会话历史、SKILL.md 加载、流式对话和命令行入口 |
| `safety` | 六轴 URDF 范围、编码器映射交集及发送速度约束 |
| `imitation` | 实体/键盘主臂、LeRobot 记录、ACT 训练和策略回放 |
| `reinforcement` | table 人机回环、SAC 学习器/执行者、人工奖励与视觉奖励训练 API |
| `contracts.py` | 共享观测、动作类型，关节位置单位为弧度 |

复用本机已有 Conda `base` 环境。本次 ACT 数据记录、训练和推理已实际跑通，无需转 UV。运行依赖包含 `lerobot[feetech]==0.4.4`、`mujoco==3.15.0`、`openai==2.24.0`、PyYAML、NumPy，记录在 `pyproject.toml`。在本目录执行：

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

2026-11-01 已在现有 `base` 安装上述三件套（版本后缀 `+cu126`），识别 RTX 4060 Laptop GPU。SymPy 随之更新到 1.14.0；ACT 已完成小规模 GPU 参数更新和检查点推理，未进行性能基准或任务成功率验收。

共享 `base` 尚非全部依赖兼容：本次升级超出 `lightx2v==0.1.0` 对 torch/torchaudio≤2.8.0、torchvision≤0.23.0 的声明范围，LightX2V 运行未验收。原有 LeRobot 与 `diffusers==0.38.0.dev0`（要求 <0.36.0）、OSAM 与 `onnxruntime==1.20.1` 的依赖冲突也尚未处理，不能据此认为完整 LeRobot 训练已可运行。

## 库入口

```python
from pathlib import Path
from xiaoxia_core.integrations import LeRobotDatasets
from xiaoxia_core.simulation import MujocoSimulation, SimulationConfig

# 在 core 目录运行，使用独立的 SO-100 模型；不改动前端 SO-101 展示。
urdf = Path('assets/so100/so100.urdf')
with MujocoSimulation(SimulationConfig(urdf_path=urdf)) as simulation:
    observation = simulation.read_observation()
    observation = simulation.step()

# 读取已有本地 LeRobot 数据集，不下载视频。
# dataset = LeRobotDatasets.open('local/so101', Path('data/so101'))
```

`MujocoSimulation` 实现 `RobotTransport`，可直接传给 `CollectionService`。`send_action` 仅更新目标，`step` 才推进物理时间；观测时间戳来自仿真时间，与实机时钟不同。默认固定步长 0.002 秒，重力采用 MuJoCo 默认值，底座固定。

位置控制使用有力矩上限、目标速度约束、隐式阻尼和重力偏置补偿的控制器；参数未经实机标定。导入时显式排除直接相邻 link 接触，保留其他自碰撞，并通过内存网格解决 Windows 中文路径问题。小幅主从轨迹已验证，完整接触精度与实机稳定性未验收。模块不自动打开渲染窗口、不驱动物理设备。

`LeRobotDatasets.create` 返回原生 `LeRobotDataset`。`imitation.DemonstrationWriter` 已接入原生记录及 finalize；原有 JSONL 记录器仍是另一种格式，尚无转换器。`imitation.act` 提供 ACT 训练和本地策略加载，不依赖全量策略工厂，也不自动下载视觉骨干权重。

调用方用上下文管理器管理 `RobotTransport` 和 `EpisodeRecorder`，再将它们传给 `CollectionService`。采集节拍由调用方决定；图像记录为路径，图像文件由数据源保存。

SO 系列串口、可选 OpenCV 相机、ACT 训练与推理入口已实现。实机运行须先完成设备身份、校准和 URDF 映射确认；当前尚未通过实机示教/抓取验收。操作命令和本次证据见 [模仿学习说明](docs/imitation.md)。

模型服务另提供 [模仿学习 HTTP API](docs/imitation-api.md)：按 episode 记录模型关节与统一相机画面、导出原生 LeRobot 数据集、后台 ACT 训练、预测与回放，以及任务进度和停止接口。默认在仿真执行；ACT 策略可选择真机串口，配合使能、失能积木闭环执行，实机抓取效果尚未验收。

[红色物体跟随](docs/red-tracking.md) 提供相机分类积木和 Python API，通过颜色检测让随臂相机对准目标，复用原相机窗口显示目标框；支持仿真和已使能真机，不执行抓取。

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

桌面 Agent 已启用 MCP 工具循环，支持模型、RL 和当前 WebView 积木控制，详见 [Agent MCP](docs/agent-mcp.md)。未提供实机运动工具；技能仍由用户显式选择。流式接口依据 [OpenAI 流式响应文档](https://developers.openai.com/api/docs/guides/streaming-responses)。未发送实际 API 请求，尚未验收联网交互。

## 强化学习 API

[强化学习 HTTP API](docs/reinforcement-api.md) 复用模型服务 8766 端口和原生 LeRobot SAC，提供会话、转换数据、人工接管/成功反馈、ROI、学习器、执行者、单次预测、奖励分类器及后台任务停止。当前目标仅为 table，使用关节增量与 HTTP/SQLite 适配；不是官方实机末端空间/gRPC 流水线。服务启动不会初始化策略或自动训练。

## 仿真与真机采集 API

[采集 HTTP API](docs/collection-api.md) 提供 MuJoCo 物理状态/图像采集、只读真机编码器/图像采集和原生 LeRobot Dataset v3 保存。通过命令回执管理逐帧记录、episode 和 finalize；成功完成且含动作标签的会话可接入已有 ACT 训练接口。真机默认只读，不自动连接、不使能力矩。


### LLM 本地配置

在工作区根目录 `.env` 中填写 `OPENAI_API_KEY`、`OPENAI_MODEL`；兼容服务可另填 `OPENAI_BASE_URL`，留空使用SDK默认地址。字段模板为根目录 `.env.example`。桌面Agent启动、LLM配置读取和LLM客户端创建时自动加载，不依赖当前目录；优先级为进程环境 > core/.env > 根目录.env。`.env`已由Git忽略，真实密钥不提交，前端不接收密钥。修改后新请求/新建客户端读取配置，已有进程环境中的同名变量仍优先。

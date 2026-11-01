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
| `contracts.py` | 共享观测、动作类型，关节位置单位为弧度 |

复用本机已有 Conda `base` 环境，不创建独立环境。依赖固定为 `lerobot==0.4.4`、`mujoco==3.15.0`，版本记录在 `pyproject.toml`，不自动升级已有 PyTorch。在本目录执行：

```powershell
conda activate base
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
```

以上 `PYTHONPATH` 仅对当前 PowerShell 会话生效，之后可直接导入 `xiaoxia_core`。`pyproject.toml` 保留包元数据，后续运行依赖统一记录在其中，使用 Conda 管理已有 `base` 环境。

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

# core

Python 3.11+ 核心，使用标准库实现基础层，具体设备和算法通过类接口接入。

| 模块 | 职责 |
| --- | --- |
| `collection` | 单帧采集与 JSONL episode 记录，已有文件不会覆盖 |
| `communication` | 设备连接、观测读取、动作发送的抽象接口 |
| `training` | 训练配置、结果和算法适配接口 |
| `inference` | 策略加载、状态重置、观测到动作的推理接口 |
| `contracts.py` | 共享观测、动作类型，关节位置单位为弧度 |

在本目录使用 Conda 管理环境：

```powershell
conda env create -f environment.yml
conda activate xiaoxia-core
python -m pip install --no-build-isolation --no-deps -e .
```

后续依赖统一添加到 `environment.yml`，执行 `conda env update -f environment.yml --prune` 更新。`pyproject.toml` 仅定义 Python 包元数据。

调用方用上下文管理器管理 `RobotTransport` 和 `EpisodeRecorder`，再将它们传给 `CollectionService`。采集节拍由调用方决定；图像记录为路径，图像文件由数据源保存。

当前为模块基础骨架。尚未实现 SO-ARM-101 串口协议、摄像头、训练算法、推理模型、桌面 IPC。训练和推理必须注入真实适配器；推理只返回动作，不自动发送到设备。

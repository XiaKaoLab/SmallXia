# SO 系列主从与模仿学习

复用 Conda `base`；本次不转 UV，不修改 `table`。SO-100/101 共用六关节通信、数据格式和 ACT 链路，模型/校准/零点方向由配置决定。

## HTTP API

模型示教、统一相机画面记录、LeRobot 数据集导出、ACT 训练、预测、table 回放及任务停止接口见 [模仿学习 API](imitation-api.md)。HTTP API 不连接实机，沿用 base 环境和模型服务 8766 端口。

## 软件入口

实际脚本入口为 `core/src/xiaoxia_core/imitation/__main__.py`。在 `core` 目录执行：

```powershell
conda activate base
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
$env:USE_TF = '0'

# 模型与命令限位审计
python -m xiaoxia_core.imitation audit

# 目录须为新目录，避免覆盖旧数据或模型
python -m xiaoxia_core.imitation sim-record --dataset data/so100-demo --frames 60 --episodes 2
python -m xiaoxia_core.imitation train --dataset data/so100-demo --output checkpoints/so100-act --steps 1000 --device cuda
python -m xiaoxia_core.imitation sim-rollout --checkpoint checkpoints/so100-act --frames 30
```

默认模型为 `core/assets/so100/so100.urdf`。SO-101 可用顶层 `--urdf` 指定对应文件；前端模型不作为 SO-100 实机标定依据。

示教保存从臂观测和实际发送的有界目标，六轴统一弧度。相机配置非空时记录 RGB 图像；无相机时使用关节状态，ACT 所需 `environment_state` 只是当前关节状态的副本，不含未来目标。这是关节状态模仿基线，不能证明视觉抓取能力。

ACT 使用 LeRobot 原生策略和数据集，固定关节顺序，按记录时关节上下界线性归一化；检查点包含归一化元数据，须用本项目的 `ACTJointPolicy` 加载，未导出官方完整 processor pipeline。输出越界直接报错，发送端再限制速度和编码器目标。仿真数据训练的检查点禁止直接发给实机。

## 实机与虚拟主臂

当前确认只有 COM17 从臂，没有实体主臂。`KeyboardLeader` 可替代示教主臂，从从臂当前姿态初始化：1–6 选轴、`+/-` 每次 0.01 rad、空格重新同步、Q 停止。它需要 Windows 交互终端，不自动运行脚本运动。

复制 `configs/so100.example.yaml` 为 `configs/so100.local.yaml`，填写：

- `device_identity_confirmed`：只在操作者确认设备身份后设为 true，不能仅由串口描述或电机应答推断。
- `follower.port`：当前从臂为 COM17。`calibration` 指向实际独立校准文件。
- `follower.mapping`：指向测量后的 URDF 零角/方向文件。格式见 `joint-mapping.example.json`，不得直接把校准区间中点当 URDF 零点。
- `leader.kind`：无实体主臂使用 keyboard；以后接入实体主臂时改 hardware，并填写另一端口及独立校准/映射。
- `cameras`：可选相机名称到 OpenCV 索引的映射，默认 640×480。

先按官方流程校准两臂各自的实际运动范围。校准会涉及 EEPROM，项目连接路径不自动写 ID、波特率、Homing Offset 或工作模式。若模型零点不可直接到达，应使用多个已知角度测量拟合偏移，而不是强行推至硬限位。

```powershell
# 配置完整且校准匹配后才可执行
python -m xiaoxia_core.imitation inspect --profile configs/so100.local.yaml
python -m xiaoxia_core.imitation teleop --profile configs/so100.local.yaml --seconds 20 --enable-motion --workspace-clear
python -m xiaoxia_core.imitation record --profile configs/so100.local.yaml --dataset data/so100-real --repo-id local/so100-real --seconds 20 --episodes 1 --enable-motion --workspace-clear
# 使用真实示教数据训练后，再用 rollout 加载真实检查点
python -m xiaoxia_core.imitation rollout --profile configs/so100.local.yaml --checkpoint checkpoints/so100-real-act --seconds 5 --enable-motion --workspace-clear
```

连接时只读校准、位置、模式和力矩；校准与设备不一致或位置超出交集即拒绝动作。使能前将目标寄存器同步到当前位置并回读确认；断连/异常关闭力矩。运行结束必须确保机械臂有安全支撑。控制超时检查发生在发送路径，不宣称具有独立硬件看门狗。

键盘示教只适合小幅、低速的关节示教，不等同于两台实体臂，也不能替代碰撞规划、力控和真正急停系统。

## 2026-11-01 已执行证据

| 项目 | 实际结果 |
| --- | --- |
| 固定 SO-100 模型 | 上游提交 `a758567c3978dfeefe282ede0500085a48fe8f78`，13 个 STL，SHA256 见 provenance |
| 模型限位 | MuJoCo 编译范围与 URDF 一致，12 个边界目标接受、12 个越界目标拒绝，审计本身 0 物理步 |
| 仿真示教 | 2 episodes、64 帧，脚本运动学主臂 + 动力学从臂，峰值速度 0.148607 rad/s，峰值跟随误差 0.011658 rad |
| ACT 训练 | CUDA、20 次真实优化器更新，loss 79.22479 → 22.37078；不是模型质量验收 |
| 检查点推理 | 本地重载后 30 帧仿真回放完成，位置保持模型范围内、峰值速度 0.153534 rad/s；任务成功率未验证 |
| 实机读取 | 用户确认 COM17 为从臂；仅识别/读取，0 力矩写入、0 EEPROM 写入；COM31 未通过预期握手 |
| 实机阻碍 | COM17 夹爪读数 945，设备保存范围 1090–2660；本机两份旧校准均不匹配设备；URDF 零点映射未确认 |

原始报告位于 `core/data/validation/so100-limits.json`、`so100-record.json`、`so100-training.json`、`so100-rollout.json`、`serial-read-only.json`。有效示教位于 `so100-demo-v4`，检查点位于 `core/checkpoints/so100-act-validation`；均为本机生成文件，未提交。此前失败的仿真记录目录保留作诊断，不作为通过证据。

结论：软件的采集→训练→加载→仿真推理已跑通；尚未完成实体从臂示教、实测硬限位标定、真实抓取或两台实机联动。

参考：[用户指定 SO-100 中文文档](https://hugging-face.cn/docs/lerobot/so100)、[官方 SO-101 文档](https://huggingface.co/docs/lerobot/so101)、[官方模仿学习流程](https://huggingface.co/docs/lerobot/il_robots)。


## 官方校准与真机映射

“机械臂”分类的“校准机械臂”和“映射真机到仿真”均先读取六轴 EEPROM 校准快照。优先查找官方校准目录中与六轴 ID、方向、Homing_Offset、range_min、range_max 完全匹配的 JSON；已有文件不匹配时绝不将它覆盖到设备。如果 EEPROM 中已有结构有效、非出厂全量程的行程数据，直接导出为官方格式 JSON 并复用，不重复采集。该匹配是设备配置指纹，不是电机唯一序列号认证，也不证明历史端点采集的精度。

没有有效数据时进入手动向导：安全支撑并保持六轴力矩关闭、位置模式；将各关节放到行程中部，点击“记录中位并检查行程”。此时调用当前安装版 LeRobot 的 set_half_turn_homings，然后按 M1 到 M6 逐轴显示最小、当前、最大编码器值，手动走到两端并确认。非全周关节变化少于 100 刻度不能确认。腕部旋转按官方全周特例设为 0～4095，其余关节使用观测极限。最后写入偏移和范围、读回核对并保存官方格式文件。中途停止或租约到期会尝试恢复校准前快照；恢复失败明确报错。突然断电或进程被强杀无法保证自动恢复，原始快照保存在会话的 calibration-before.json。整个过程不自动驱动、使能力矩或切换模式。

单位显式区分：Present_Position 使用 normalize=False，输入是已应用 Homing_Offset 的编码器计数，不重复减偏移。五轴按本机 LeRobot DEGREES 公式 `(tick - (range_min + range_max) / 2) * 2π / 4095` 转成 URDF 弧度；当前 so101_new_calib 模型也采用行程中点零位，不做 ±180° 折返，不在每次连接重新归零。夹爪遵守官方闭合 0、张开 100 的比例，再转换到模型 0～upper 的角度。这是用于显示的线性近似，不是精确夹爪几何标定。实机 SO-100 与显示 SO-101 的方向、几何一致性仍需逐轴人工核对，geometry_verified 和 verified_for_motion 保持 false。

运行回执 display_alignment 启动持久 alignment_preview 流；alignment_stop 停止并释放串口。新桥动作 arm_calibration_action 接受 session_id、stage（center/range）和 index（-1/0..5），只接受当前步骤，防止双击跳过关节。界面断流后租约最多 10 秒到期。新运行会先停止同串口旧会话。

映射积木直接检查并复用官方数据，不要求先运行另一个校准积木；两个积木同时启用仍提示分开运行，避免串口争用。每帧固定发送至 table 模型路由，验证目标为非物理 display_target。关节范围和碰撞路径继续限制模型姿态；面板区分测量值与实际采用值，保留实机超出设备校准范围的提示。播放录制期间不启动映射。历史录制回放仍属于相对仿真回放，此处不改变它的语义。

依据：
- https://huggingface.co/docs/lerobot/so100#calibrate
- https://huggingface.co/docs/lerobot/main/cheat-sheet#calibration
- https://github.com/TheRobotStudio/SO-ARM100/blob/main/Simulation/SO101/README.md
- 当前 Conda base 安装版 lerobot/robots/so_follower/so_follower.py 与 lerobot/motors/motors_bus.py。

2026-11-02 COM17 实机检查：读取并复用现有 EEPROM 校准，已导出官方格式文件；校准寄存器写入次数 0，无实机运动指令。读取单位 encoder_ticks，输出 rad；停止后 disconnected=true。夹爪当前位置仍超出设备已存范围，界面保留异常提示，不据此宣称历史校准精确。逐轴向导、腕部全周特例和取消回滚仅通过假总线验证，未在实机重新走端点。证据见 official-calibration-check.json。

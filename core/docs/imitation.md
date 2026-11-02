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


## 积木显示对齐

“机械臂”分类中的“校准机械臂”积木选择 COM 口，并填写六轴在 URDF 坐标中的已知参考角度（度）和正反方向。先手动将安全支撑、力矩关闭的实机摆到已知姿态，再运行。默认 0° 只是输入初值，不代表当前实机零点。程序保存固定零点 `zero_tick = reference_tick - direction × reference_rad × 4095 / (2π)`，跟随按 `angle_rad = direction × (tick - zero_tick) × 2π / 4095` 计算；不再读取当前仿真姿态，不做 ±180° 差值折返。零点和方向的物理准确性仍需人工逐轴核对；它不是 LeRobot 电机行程校准，不产生可用于实机运动的已验证映射。

显示角度由参考角度加上有向编码器增量得到，跨零按最近一圈解释；不支持通过一次采样推断多圈旋转。模型显示继续受关节限位和碰撞约束，可能停在边界，角度面板保留测量值。设备范围异常单独提示，不改写或掩盖。

运行结果中的 `display_alignment` 回执启动持久 `alignment_preview` 桌面流；“停止跟随”调用 `alignment_stop`。前端退出或断流后租约最多 10 秒到期，工作进程释放串口；重新对齐会先停止该串口的旧会话。后台训练不停止，跟随时临时隐藏并行训练场景，停止后恢复。参考关系写入 `core/data/display_alignment/<id>/alignment.json`，标记 `verified_for_motion=false`，不会覆盖硬件配置。

2026-11-02 COM17 检查：积木已启动只读流，界面显示六轴角度与夹爪范围异常，停止按钮使会话进入 stopped，原工作区恢复。调试命令桥出现回执超时，未重发启动命令；随后通过实际 UI 和会话文件确认执行结果。没有驱动实机，未验证人工摆放是否匹配或各轴运动方向。TypeScript 与 Python 语法检查通过，未完整构建。


## 编程区真机映射

“机械臂”分类新增“映射真机到仿真”（table_map_hardware_arm）积木，TARGET 选择发现的串口。先单独运行“校准机械臂”，人工核对仿真与实机起点、六轴方向，完成后禁用或移除该校准积木，再运行映射积木。映射使用同串口最近一次固定零点校准（`angle_basis=fixed_urdf_zero_v1`），不在每次启动时重新把当前读数当零点；同时运行校准和映射积木会明确提示分开操作。

后端 `DisplayAlignment.start_mapping(port)` 返回 mode=mapping 的会话，加载保存的参考角度、编码器起点和方向。连接时只读核对六轴设备校准快照，变化时要求重新对齐，不自动修正 EEPROM。读取仍要求力矩关闭，任意写寄存器和力矩方法均被只读总线覆盖为报错。

每次读取后把映射角度限制到 URDF 范围，固定发送到 `http://127.0.0.1:8766/api/v1/robots/table/motions`；目标必须声明为仿真 display_target，不接受动态 robot_id/URL。模型继续使用既有碰撞路径限制，流中区分 joint_positions（映射测量值）和 applied_joint_positions（模型应用值）。面板标题“真机 → 仿真”，显示六轴角度，受限时用箭头显示实际采用值，保留设备校准范围异常提示。停止后模型保留最后应用姿态，真实串口释放；播放录制期间不启动真机映射。

开发桥动作 `alignment_map` 传 port；`alignment_preview`、`alignment_stop` 传 session_id。流为持久连接，不为每帧启动 Python 或 LLM；界面断开后租约到期退出。软件映射约定不构成实机控制用的绝对角度标定，人工起点和方向确认仍是几何对应的前提。

2026-11-02 通过当前 WebView 的映射积木联调 COM17：反馈时间戳连续更新，停止后的 table API 角度与最后应用值一致，串口已释放，原工作区完整恢复。仅调用实机读指令，未发送实机运动指令；夹爪设备范围异常仍保留。证据见 arm-mapping-check.json。TypeScript、Python 语法检查通过，未执行完整构建。

旧的相对显示对齐记录不能自动转换成已确认物理零点，因此真机映射会要求重新填写参考角度并校准。设备校准快照变化时仍要求重新校准；读取异常单圈范围会停止。历史录制回放仍明确属于相对仿真回放，本次不改变其语义。

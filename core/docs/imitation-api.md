# 模仿学习 HTTP API

Created on 2026-11-02; Updated on 2026-11-08
@author: https://github.com/Linmoqian

沿用本机 `http://127.0.0.1:8766`、现有 Conda base 和 `lerobot==0.4.4`。所有接口需要 `Authorization: Bearer <XIAOXIA_MOTION_TOKEN>`，POST 使用 JSON 对象。实现复用 `DemonstrationWriter`、`ACTTrainer`、`ACTJointPolicy`，不执行 shell 字符串、不创建环境、不上传 Hub。

流程参考 [LeRobot 0.4.4 模仿学习文档](https://huggingface.co/docs/lerobot/v0.4.4/il_robots)：记录 episode → 原生 LeRobotDataset → ACT 参数训练 → 检查点预测/评估。此 API 使用本项目的六关节弧度与归一化约定，不接受任意 Hub 数据集或外部检查点。

## 路由

下表路由均以 `/api/v1/imitation` 为前缀。`dataset_id`、`job_id` 都是服务生成的 32 位标识，不能作为任意文件路径使用。

| 方法 | 路由 | 请求与行为 |
| --- | --- | --- |
| POST | `/datasets` | `{"task":"移动到目标姿态","fps":2,"cameras":["virtual"]}` 创建记录会话，201 |
| GET | `/datasets` | 列出本地会话及导出状态 |
| GET | `/datasets/{dataset_id}` | 查询帧数、已保存 episode、图像来源和导出任务 |
| POST | `/datasets/{dataset_id}/frames` | `{"action":{六关节弧度目标}}` 读取当前 table 状态和配置的相机帧，保存一个示教样本，201 |
| POST | `/datasets/{dataset_id}/episodes` | `{}` 保存当前 episode，至少两帧，下一帧进入新 episode |
| POST | `/datasets/{dataset_id}/finalize` | `{}` 保存未结束的 episode 并关闭记录；异步导出 LeRobotDataset，202 返回任务。重复调用复用运行中/成功的导出，失败可重试 |
| POST | `/trainings` | `{"dataset_id":"…","steps":1000,"batch_size":4,"chunk_size":16,"device":"cuda"}` 创建 ACT 训练任务，202 |
| POST | `/predictions` | `{"training_job_id":"…","device":"cpu"}` 使用最新 table 状态及检查点需要的相机帧预测一次，202；结果不发送动作 |
| POST | `/rollouts` | `{"training_job_id":"…","steps":10,"fps":2,"device":"cpu"}` 预测并向 table 发送模型动作，202 |
| GET | `/jobs` | 列出任务 |
| GET | `/jobs/{job_id}` | 查询状态、进度、结果/错误及最多 8 KB 日志尾部 |
| POST | `/jobs/{job_id}/stop` | `{}` 停止后台任务，已完成任务保持完成状态 |

`frames.action` 必须完整包含 `shoulder_pan`、`shoulder_lift`、`elbow_flex`、`wrist_flex`、`wrist_roll`、`gripper`，单位 rad，满足当前 SO-101 URDF 限位。记录接口只保存显式动作标签，不发送该动作，不从当前姿态猜测标签。调用方负责提供与当前观测对应的示教目标，并通过已有模型运动 API 执行示教。

`fps` 为名义采样频率，调用方按节拍提交样本；接口拒绝过快提交和重复使用同一相机帧，但不会自动补帧或重采样。原始接收时间保留在 staging JSONL，相机与关节并未硬件同步。包含 virtual 相机时 fps 上限为 2；无虚拟相机时记录 fps 为 1–60，回放为 1–30。长时间间断应结束当前 episode，再开始下一段。

## 数据与任务状态

记录会话状态为 `recording` → `closed`，是否已导出由 `export_status` 和 `export_job_id` 表示。只有导出任务 `succeeded` 才能启动训练。

任务状态为 `queued` → `running` → `succeeded` / `failed` / `cancelled`。服务重启发现未完成任务时标记 `interrupted`，不自动恢复。后台工作进程监测宿主退出，避免服务异常退出后继续训练或回放。当前只允许一个模仿学习后台任务运行，避免同时占用 GPU 或争用回放控制。

- 导出进度：`frames`、`total_frames`。
- 训练进度：`step`、`total_steps`、`loss`；结果包含检查点路径和训练报告。
- 单次预测结果：`joint_positions`、`unit:rad`、`executed:false`、`physical:false`。
- 回放进度：`step`、`total_steps`、`last_receipt`；动作经过 0.25 rad/s 上限和已有模型碰撞边界裁剪。任务停止后不再发送新目标，已经提交的模型目标保留；不表示独立硬件急停。

停止或失败的任务可能保留部分输出，但不能作为成功检查点/数据集使用。重试导出或训练会生成新任务目录，不覆盖旧结果。当前训练只在完成后保存检查点，不提供中途断点续训；停止训练需要重新发起训练任务。

数据默认保存在 `core/data/imitation_api/`，已由现有数据目录忽略规则排除提交。每个会话含 manifest、逐 episode JSONL 和 JPEG；每个任务含请求、状态、日志及完成后的原生数据集或检查点。

## Python 调用

在现有 core 运行环境使用客户端，令牌从环境读取：

```python
from xiaoxia_core.imitation.api_client import ImitationClient

api = ImitationClient()
dataset = api.create_dataset("移动到目标姿态", fps=2, cameras=["virtual"])
dataset_id = dataset["id"]

# 先显式装配相机、保持 table 运行。按每 0.5 秒一个样本提交多个真实示教目标。
# api.record_frame(dataset_id, action={...完整六关节目标...})
# api.save_episode(dataset_id)
# export_job = api.finalize(dataset_id)
# api.job(export_job["id"])  # 等待 succeeded
# training = api.train(dataset_id, steps=1000, chunk_size=16, device="cuda")
# api.job(training["id"])    # 等待 succeeded
# prediction = api.predict(training["id"])
# api.job(prediction["id"])  # result 中获取动作；不会执行
# playback = api.rollout(training["id"], steps=10, fps=2)
# api.stop(playback["id"])
```

## 来源与执行范围

当前 API 的关节观测来自 `table_display_target`，不是 WebView 实际渲染到位回执，也不是串口实机反馈。原生数据集标注 `simulated:true`、`robot_type:so101_table_model`。即使 `cameras` 含 real，也只是“模型状态 + 真实相机图像”，不构成真实机械臂示教。相机来源及非同步属性写入数据集附加元数据。

无相机时沿用关节状态模仿基线；有相机时记录 RGB 图像并作为 ACT 视觉特征。当前虚拟相机低帧率、场景和数据质量仍限制策略效果；任务完成、训练 loss 或成功导出都不等于抓取成功率验收。默认回放目标为 table；指定 `target:serial:COM17` 时走下面的真机链路。

## 真机使能、策略和失能

积木按顺序拼接：`使能机械臂 COM17` → `运行示教模型（目标 COM17）` → `失能机械臂 COM17`。原有程序默认仍在仿真运行。

| 方法 | 完整路由 | 行为 |
| --- | --- | --- |
| POST | `/api/v1/hardware/arms/COM17/enable` | `{"profile":"so100.local.yaml"}`，显式使能并记录当前姿态作为本次起始位置；返回 202，已有同配置会话复用 |
| GET | `/api/v1/hardware/arms/COM17` | 查询真实反馈并维持控制心跳 |
| POST | `/api/v1/imitation/rollouts` | `{"training_job_id":"…","target":"serial:COM17","steps":20,"fps":2,"device":"cpu","camera_source":"opencv_…"}`，创建真机 ACT 闭环任务 |
| POST | `/api/v1/hardware/arms/COM17/disable` | `{}`，请求缓慢回到本次起始位置再失能，返回 202；继续查询直到 `stopped` 且 `release.torque_disabled:true` |

真机不自动使能。Python `HardwareClient.enable()` 维持心跳，`disable()` 等待回位及力矩关闭确认；直接 HTTP 调用者需在持有控制期间维持心跳。模型加载期间也包含在此期间。

策略读取实测六轴反馈，以 `render_joint_positions` 转到训练模型坐标；预测经过 0.15 rad/s 上限，再由硬件控制器逆转换到编码器控制坐标，沿用现有平滑轨迹。每轮重新读取反馈，最后一步等待实际到位。进度和结果标注 `physical:true`、串口与反馈，不把下发成功当成抓取成功。

动作回执包含 `motion_id`、`applied_motion_id`、`reached_motion_id`，到位只确认对应目标。推理结束后按最新反馈及实际周期计算下一目标，驱动器同时限制策略速度；控制循环按 30 Hz 节拍调度，不额外叠加每轮串口处理时间。等待到位与回位按位置是否持续接近目标识别停滞，不设置正常动作的总时长上限。

真实策略图像在内存解码缩放，同轮同源图像只读取一次。任务阶段为 `loading_policy`、`warming_policy`、`inferencing`；预热不下发动作，结束后清空动作队列。进度保留 `inference_ms`、`capture_ms`、`cycle_ms`、`effective_fps`、观察及执行反馈时间和相机接收时间，方便区分模型、相机、控制延迟；这些时间不代表硬件同步。CPU 推理默认使用两个计算线程，可通过 `XIAOXIA_INFERENCE_THREADS` 调整。

视觉策略的 `camera_source` 为所选真实摄像头，按模型尺寸缩放；多相机模型可用 `camera_sources` 显式映射各模型图像键。未提供映射时，仅接受模型本身的真实相机键，不能将虚拟图像当作实拍。仿真训练的视觉策略在实机上的效果尚未验证。此链路面向当前 `so100_mid_calib` 坐标的 ACT 检查点；抓球 SAC/ONNX 的仿真环境观测尚未迁移到真机。

```python
from xiaoxia_core.communication.hardware_client import HardwareClient
from xiaoxia_core.imitation.api_client import ImitationClient
from xiaoxia_core.blocks.workflow import BlockWorkflow

arm = HardwareClient('COM17')
try:
    arm.enable('so100.local.yaml')
    job = ImitationClient().rollout(training_job_id, target='serial:COM17', steps=20,
                                   camera_source='real')
    BlockWorkflow().wait_job(job)
finally:
    arm.disable()
```

停止真机策略任务或推理失败会请求回位失能。任务正常完成保留当前使能状态，供后续积木衔接；程序结束仍沿用控制释放清理。失联由已有控制会话处理。故障下是否返回起始位置、是否关闭力矩以实际 `release` 结果为准。

停止任务先终止推理进程，再独立请求失能，不等待网络请求完成才停止推理。任务的 `release_request.status` 为 `pending`、`requested` 或 `failed`，请求失败保留原因；`requested` 仍只表示请求成功，失能完成需查看硬件会话 `release.torque_disabled`。

桌面模型持续订阅实测反馈。没有控制会话时，按已确认的 `so100.local.yaml` 建立只读连接；回位失能后继续读取关节，手动摆动也会更新模型，标记 `read_only_following:true`。只读连接不调用使能或运动写入，不刷新控制租约；断开时保留最后实测姿态并等待重新读取，不用仿真目标替代。

`POST /api/v1/hardware/arms/COM17/observe` 可显式建立同样的只读跟随。再次使能会先停止只读线程、释放串口。录制和显示对齐通过 `observe-stop`／`observe-resume` 交接串口；控制期间禁止这类交接。前端只使用转换后的 `render_joint_positions` 显示真机，不把原始控制坐标直接当作模型角度。

2026-11-08 真机排查状态：COM17 的本机配置已设 `follower.software_pid_enabled: false`，运动和回位均完全旁路软件 P/I/D，只下发限速、限加速度的位置轨迹。原补偿参数保留，修改配置在下次连接时生效；会话 `software_pid_enabled`、`stabilizer: trajectory_only` 可核对实际模式。外环关闭的 M4 30° 往返仍由操作者确认明显抖动，真机运动尚未验收，不应将停稳误差或仿真策略成功记录作为上真机策略的依据。

后续按要求切换为 `follower.trajectory_mode: servo`（缺省亦为 servo）：每次新终点只写一次 Goal_Position，由舵机内部速度、加速度执行；相同终点与速度不重复写入，反馈读取继续。会话显示 `stabilizer: servo_profile`、`servo_goal_writes`、`servo_speed_registers`。软件 PID 在此模式不生效。使能时保存 SRAM 速度/加速度，回位同样发送起始终点并等待实测到位，失能后恢复 SRAM；不改 EEPROM Phase 或 PID。速度按 Phase BIT2 对应的单位换算，向下量化，低于舵机有效分辨率报错，不能用速度 0 冒充慢速；多轴同步发出，不保证同一时刻到达。

2026-11-08 `20261108-154245` 完成内部轨迹 M4 45° 往返，`servo_goal_writes=2`（去程、回程各一次），往返各阶段内 Goal_Position 不再逐帧改变；回位失能成功。外伸端静态误差约 0.78°，最大编码器单步仍为 8 格，尚未确认肉眼平滑度改善。重复该模式使用 `python core/scripts/diagnose_joint_motion.py --trajectory servo --degrees 45 --cycles 1 --hold 17`；诊断脚本默认仍为 software，便于与旧数据对照。

`python core/scripts/diagnose_joint_motion.py --mode off --degrees 30 --cycles 2 --hold 14` 可重复这组基础运动；`--mode compare` 对照外环关闭/开启。脚本独占串口采集原始目标寄存器、编码器、速度、电流、负载代理、电压和状态，结束回位失能后恢复后台只读连接。结果与腕部相机录像位于 `core/data/motion_diagnostics/`；相机和总线按主机接收时间对齐，非硬件同步，低帧率录像不能证明高频振动不存在。

`--compare-p --degrees 45 --cycles 1 --hold 17` 对比原参数与 M3/M4 内部 P=16、8；`--p-values 8` 只比较原参数和 8，`--joint elbow_flex` 改测 M3。调参前保存原始 P，仅在失能时解锁、写入并读回，保留原 Lock，每轮回位失能后恢复原始 P；不改 I、D、死区和最小启动力。`parameters` 与 `parameters_after` 比较的是该轮实验参数；正常清理恢复后的参数需再次读回核实。日志包含最小启动力原始寄存器值，不把社区帖子中的“5N”当作可直接写入的物理单位。

2026-11-08 内环对照：`20261108-152754` 为 M4 30°、原始 P/16/8；`20261108-153001` 为 M4 45°、原始 P/8；`20261108-153147` 为 M3 45°、原始 P/8。原始六轴 P 为 16/16/32/24/16/16。降低到 8 没有降低最大编码器跳步，M3 外伸端停稳误差绝对值由约 0.34° 增到 1.22°，不能按社区案例直接认定有效或永久应用。原参数也未通过运动稳定验收。

重复 `20261108-153331` 的 M4 45° 对照后，操作者确认 P=8 肉眼抖动明显减轻；这与“最大编码器单步没有改善”是不同指标，不能相互替代。随后保留 M4 内部 P=8，M3 保持 32，其余四轴保持 16；I=0、D=32、死区与最小启动力均未更改，软件外环继续关闭。写入与读回备份为本机 `core/data/motion_diagnostics/20261108-m4-applied.json`。这是局部改善，尚不构成整机、全姿态或策略运行稳定验收。

运动与回位使用低增益外环 PID 消抖：默认 P=0.12、I=0、D=0.015，测量及微分低通，默认修正最多 4 个编码器刻度，再经过加减速轨迹。小于 2 个刻度的目标变化会合并；误差连续五帧不超过 3 个刻度、参考轨迹到位且反馈及命令速度较低后锁定命令，实际偏移超过 4 个刻度或新目标会解锁。一个刻度约 0.088°，这些条件不代表机械绝对精度。

本机 YAML 的 `follower.pid_load_compensation` 可按关节配置 `{ki: 0.4, max_trim_deg: 2}`，也可增加 `kp`、`kd` 单独调整比例与微分阻尼。仅在参考轨迹到位且反馈速度较低时缓慢积分，积分及最终修正均限幅，饱和后不继续向饱和方向累积；进入稳态保留已有补偿；连续更新目标时同样保留积分，避免反复卸载。运动参考变化期间只保留限幅负载偏置，由舵机内环跟踪平滑参考；目标安静至少 250 毫秒、参考到位后再启用位置精修。补偿修正本身按最多 0.02 rad/s 平滑变化，再沿原加减速轨迹衔接。未配置的轴仍关闭积分；参数属于当前机械臂及负载，不能直接套用其他设备。此设置不改写电机 EEPROM 的 PID 寄存器。回位仍沿用起始姿态端点约束与现有实际反馈容差，不能把 `start_reached` 当成逐刻度精确返回。

反馈中的 `last_sent_goal_ticks` 是最近下发的编码器目标，`pid_load_compensation` 是当前会话实际使用的外环配置，`pid_moving_joints` 表示处于运动跟踪的轴，`pid_holding_joints` 表示已进入稳态锁定的轴，可用于区分命令反复变化与电机自身的保持抖动。它们不是额外的电机寄存器回读。

## 本次轻量检查

API 数据通路此前已用临时两帧记录检查创建、finalize 及原生 LeRobotDataset 导出，该记录不是训练示教数据。2026-11-05 另对 COM17 完成六轴逐轴小幅动作与 PID 补偿实测，记录目标、实测位置、保持波动及回位失能结果；这些结果仅对应当时姿态和负载，不能推出全行程、不同负载下的机械绝对精度。本次仅做 Python 语法检查和针对性实机联调，未构建前端或启动训练。

# 模仿学习 HTTP API

Created on 2026-11-02; Updated on 2026-11-05
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

## 本次轻量检查

完成 Python 语法检查，并在临时目录通过 API 服务对象创建两帧记录、finalize、后台导出为原生 LeRobotDataset，返回 succeeded 后清理临时文件。该临时记录仅检查数据通路，不是训练示教数据。没有启动训练、加载策略、驱动实机或构建前端。

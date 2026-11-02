# 仿真与真机采集 API

Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian

参考 [LeRobot Dataset v3 文档](https://hugging-face.cn/docs/lerobot/lerobot-dataset-v3)，复用 LeRobot 0.4.4 原生 LeRobotDataset 写入器管理 Parquet、视频、episode 边界和统计信息，不手工拼装 v3 索引。图像默认保存为 H.264 MP4，use_videos=false 可使用原生 image 特征。

服务 http://127.0.0.1:8766，前缀 `/api/v1/collection`；所有路由要求现有 Bearer 令牌，POST 使用 JSON。复用 Conda base；创建会话只保存配置，显式 start 或 record 才启动采集源。

| 方法 | 路由 | 行为 |
| --- | --- | --- |
| POST | `/simulation/sessions` | 创建 MuJoCo 物理采集会话 |
| POST | `/hardware/sessions` | 创建只读真机采集会话，检查配置与校准映射文件 |
| GET | `/sessions`、`/sessions/{id}` | 配置、阶段、帧数、回合数、后台任务 |
| POST | `/sessions/{id}/start` | 启动工作进程，202；重复调用复用已有任务 |
| POST | `/sessions/{id}/record` | 按时长连续录制，自动启动采集并在完成后保存，202 返回 command_id |
| POST | `/sessions/{id}/frames` | 记录一帧，202 返回 command_id；需动作标签时传 action 六轴弧度目标 |
| POST | `/sessions/{id}/episodes` | 保存当前回合，至少两帧；下一帧开始新回合 |
| POST | `/sessions/{id}/finish` | 保存未结束回合、finalize、释放采集源 |
| GET | `/sessions/{id}/commands/{command_id}` | 命令 queued/running/succeeded/failed 及结果 |
| POST | `/sessions/{id}/stop` | 强制停止，部分输出不能作为完成数据；已完成会话保持完成状态 |
| GET | `/jobs`、`/jobs/{id}` | 后台进度、日志、错误和完成后的数据集路径 |

POST episodes/start/finish/stop 使用空对象。一次只运行一个采集工作进程，避免重复打开串口或共享相机。FIFO 最多排队100条；返回202不等于完成，需查询命令/会话回执。采样频率由工作进程限制，不自动无限采样。

## 仿真

```json
{"task":"机械臂移动示教","fps":10,"cameras":["simulation"],"record_actions":true,"use_videos":true,"idle_timeout_s":600}
```

使用 core/assets/so100/so100.urdf 和现有 MuJoCo 动力学控制器，读取 qpos，并从同一物理状态离屏渲染 RGB；不使用 table 显示目标替代物理反馈。无图像时 cameras=[]。

每次先取当前观测，再将显式 action 设为控制目标并推进十个子步，合计1/fps秒。动作标签是位置控制目标，不是力矩或下一帧反馈；内部控制器继续限制目标速度和力矩。初始姿态为关节范围中点，保存回合不自动归位。当前只包含单臂动力学与外部视角，不包含抓取物体、任务奖励或 table 腕部相机。

## 真机

```json
{"task":"只读编码器和相机采集","profile":"so100.local.yaml","read_only_confirmed":true,"fps":10,"cameras":[],"record_actions":false,"use_videos":true}
```

profile 只接受 core/configs 下 *.local.yaml 文件名，复用 HardwareWorkflow 的设备身份、独立校准与 URDF 映射。start 时连接 follower，核对 EEPROM 校准；不自动校准，不调用 arm，不发送实机运动目标。连接前要求力矩关闭、位置模式正确；不绕过校准失配检查。

真实状态来自校准编码器。cameras 可填 `/api/v1/cameras` 发现的 opencv_ID，也兼容已配置 real；不接受虚拟画面。关节与相机未做硬件同步，原始时间和相机元数据另存 acquisition.jsonl。正常结束释放串口及本次使用的相机；当前相机服务是共享单连接，采集期间不要另行切换设备。

默认 record_actions=false，不伪造 action，观测数据不能直接训练 ACT。外部示教需要创建时设 record_actions=true，逐帧显式提供 action；仅作为标签记录，采集接口不执行它。metadata 标记 external_target_label_not_executed。主动主从控制仍由原有 HardwareWorkflow 独立管理。

## 输出与训练

结果位于 core/data/collection_api，沿用 Git 忽略规则。任务目录保存原生 dataset、原始图像、acquisition.jsonl；会话保存配置及命令 SQLite。native timestamp 按 fps 生成，原始仿真时间/实机单调时钟另存。成功结束时 phase=completed、job.status=succeeded，结果含格式版本、帧数、回合数、来源与 dataset 路径。

成功完成且有动作标签的 collection session ID 可直接传给 `/api/v1/imitation/trainings` 的 dataset_id；观测数据或未完成数据不能训练。当前推理端仍未提供 simulation 图像源，不据此宣称视觉采集到策略回放已全部验收。

空闲超时30–3600秒，默认600秒；超时/强停的部分输出不标为完成。失败后创建新会话，不覆盖旧目录，不提供原目录续录。请求可能已推进物理时间，发生错误后先查回执，不自动重试。

## Python 与积木

```python
from xiaoxia_core.collection.capture_client import CollectionClient
collection = CollectionClient()
session = collection.create_simulation("机械臂示教", fps=10, cameras=["simulation"])
sid = session["id"]
# collection.start(sid)
# command = collection.capture(sid, action={...完整六轴目标...})
# collection.command(sid, command["command_id"])
# collection.save_episode(sid)
# collection.finish(sid)
# collection.session(sid)
```

左侧“数据”分类提供创建仿真采集、创建真机只读采集、启动、记录一帧、机械臂设定角度、保存回合、结束/停止、采集状态与命令状态。返回对象可通过变量赋值/读取积木保存。“机械臂设定角度”读取工作区滑杆值，只是目标标签，不是实机反馈。真机积木需手工勾选只读确认并填写本地配置。

本次检查完成两帧无图像 MuJoCo 到 v3.0，以及两帧 RGB 渲染到原生 Parquet/MP4 的采集、finalize 与回执。后一次临时文件清理完成。检查没有连接实机、使能力矩、训练或构建前端。真机验收仍需匹配的配置、校准与设备。


## 连续录制 API

`POST /api/v1/collection/sessions/{id}/record`，JSON 示例 `{"duration_s":10}`。无需事先 start：未启动的会话会自动连接。已开启 record_actions 的会话必须额外提供显式六轴 action；自动录制期间使用此固定目标/标签，不会从反馈伪造动作。真机入口只记录标签，不执行它。未开启 record_actions 时忽略 action，数据仍是观测数据。

时长范围 1–3600 秒，目标帧数为 ceil(duration_s × fps)，至少两帧；时长表示固定帧率数据集长度。采集与写入按目标频率节流，实际墙钟耗时包含初始化、图像采集、编码和写盘，可能更长，不承诺真实相机硬实时帧率。原始源时间戳继续保存在 acquisition.jsonl。

返回 `{session_id,command_id,status}`，202 仅表示接受。使用现有 GET 会话/命令接口查询 recording_frames、recording_target_frames、阶段和结果。相同会话重复提交相同录制参数复用原命令，不启动第二次录制；改变参数会拒绝。每段录制正常结束后关闭会话，需要新一段时创建新会话。

录制期间 POST `/sessions/{id}/finish` 提交提前保存意图，返回当前录制命令；工作进程在至少取得两帧后结束，保存回合、finalize 并释放采集源。`stop` 仍为强制停止，部分输出不算完成数据。录制期间不允许混入手动单帧或保存回合命令。正常结果包含 dataset、frames、episodes、format，以及 recording_frames、recording_target_frames、requested_duration_s、recording_wall_seconds 和 ended_early。

Python 使用 `CollectionClient.record(session_id,duration_s=10,action=None)`。积木“数据 → 录制一段”可连接采集会话、设置时长和可选动作标签；创建会话积木增加“记录动作标签”开关。录制回执可保存到变量，再用既有“采集命令状态”查询。“结束采集”提前保存，“停止采集”强停。

2026-11-02 实际 HTTP 检查通过：2 FPS、1.5 秒仿真图像录制生成 3 帧 LeRobot v3.0 数据和 1 个 MP4，视频实际可解码 3 帧；重复请求复用命令。另一段目标 50 帧的录制提前结束并正常保存 3 帧。检查只运行仿真，不连接真实设备，真机录制仍需要匹配的配置与校准。启动下一会话需等待前一采集进程退出，达到后台任务上限时接口会明确拒绝，不能据此重复提交已接受的请求。


## 原始录制的仿真播放 API

使用相同 Bearer 令牌，前缀仍为 `/api/v1/collection`。目标固定为 table 显示模型，不接受串口、设备使能或实机运动参数。

| 方法 | 路由 | 行为 |
| --- | --- | --- |
| GET | `/recordings` | 列出 core/data/recordings 下成功保存的原始编码器录制 |
| POST | `/playbacks` | 创建播放，返回 202 和播放 id |
| GET | `/playbacks/{id}` | 状态、帧号、进度、期望角度、实际应用角度和限幅情况 |
| POST | `/playbacks/{id}/pause` | 暂停；返回确认后的状态 |
| POST | `/playbacks/{id}/resume` | 从当前帧继续 |
| POST | `/playbacks/{id}/stop` | 停止；不再推进帧 |

开始请求示例：`{"recording_id":"latest_motion","speed":1}`。latest_motion 选择最近一次包含关节运动的原始录制，也可填录制目录 ID。速度范围 0.1–4；暂停、继续、停止请求体为 `{}`。一次只播放一段，正在训练或推理时不启动播放。重复开始不会产生两个并行播放，活动播放存在时明确报错；控制已结束任务不会重新开始。

当前支持 `xiaoxia_raw_encoder_v1`，不是直接加载 LeRobot v3 Parquet 数据集。开始时检查录制成功状态、帧数、六轴完整性、编码器范围、时间戳单调性和已保存的文件哈希。按采样时间间隔播放，默认 1 倍；后台用 Condition 暂停时钟，暂停期间不派发模型目标。前端通过已有模型状态轮询冻结插值，避免停在后台后画面仍追赶。播放会清除旧训练预览的显示占用，不会终止训练进程。

原始编码器尚无已验收的绝对角度映射。第一帧对齐到当前仿真姿态，随后根据有向编码器增量做相对显示：`delta_rad = direction * delta_tick * 2π / 4095`，相邻帧按最近一圈解释；无法由稀疏采样确定多圈运动。可传完整六轴 reference（弧度）和 directions（各轴 ±1），默认方向均为 +1，必须人工核实方向才能评价几何对应关系。此映射不写入实机校准，也不作为动作执行依据。

模型请求先夹到 URDF 角度范围，再经过已有碰撞路径限制；状态同时返回 requested_joint_positions、joint_positions（实际应用）和 limited。播放数据保存于 core/data/playbacks，服务重启后未结束的播放标为 interrupted，不自动恢复。

Python 客户端提供 recordings()、play(recording_id='latest_motion',speed=1,reference=None,directions=None)、playback(id)、pause_playback(id)、resume_playback(id)、stop_playback(id)。数据分类提供“录制列表”“播放录制（仿真）”“暂停播放”“继续播放”“停止播放”“播放状态”，播放回执可存入变量连接后续控制积木。

2026-11-02 实际 HTTP 验证：刚才的 99 帧真机原始运动录制，在零姿态参考下完整播放到 table 模型，确认模型目标变化；暂停 0.4 秒帧号和应用姿态均不变，继续后完成全部 99 帧；另一次播放的停止操作确认不再推进。检查未连接串口或向实机发送目标。TypeScript 与 Python 语法检查通过，未完整构建。

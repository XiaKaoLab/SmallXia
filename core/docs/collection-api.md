# 仿真与真机采集 API

Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian

参考 [LeRobot Dataset v3 文档](https://hugging-face.cn/docs/lerobot/lerobot-dataset-v3)，复用 LeRobot 0.4.4 原生 LeRobotDataset 写入器管理 Parquet、视频、episode 边界和统计信息，不手工拼装 v3 索引。图像默认保存为 H.264 MP4，use_videos=false 可使用原生 image 特征。

服务 http://127.0.0.1:8766，前缀 `/api/v1/collection`；所有路由要求现有 Bearer 令牌，POST 使用 JSON。复用 Conda base；创建会话只保存配置，显式 start 才启动采集源。

| 方法 | 路由 | 行为 |
| --- | --- | --- |
| POST | `/simulation/sessions` | 创建 MuJoCo 物理采集会话 |
| POST | `/hardware/sessions` | 创建只读真机采集会话，检查配置与校准映射文件 |
| GET | `/sessions`、`/sessions/{id}` | 配置、阶段、帧数、回合数、后台任务 |
| POST | `/sessions/{id}/start` | 启动工作进程，202；重复调用复用已有任务 |
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

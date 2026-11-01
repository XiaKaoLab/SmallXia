# 强化学习 HTTP API

Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian

流程参考 [LeRobot HIL-SERL 指南](https://hugging-face.cn/docs/lerobot/hilserl) 和 [0.4.4 版本指南](https://huggingface.co/docs/lerobot/v0.4.4/hilserl)。当前实现是面向 table 的适配：复用 LeRobot 0.4.4 原生 SACPolicy，通过 HTTP 与 SQLite 交换转换数据和权重；人工提供示教与成功/失败反馈，可选本地视觉奖励分类器。它不是官方 gRPC、实机末端位移和 IK 流水线的直接启动器。

服务 `http://127.0.0.1:8766`，统一前缀 `/api/v1/reinforcement`。所有路由要求已有 `Authorization: Bearer <XIAOXIA_MOTION_TOKEN>`；POST 使用 JSON。复用现有 Conda base，不新建环境、不自动下载视觉预训练权重、不上传 Hub、不改动前端、不连接串口。

## 会话与数据

| 方法 | 路由 | 请求/响应 |
| --- | --- | --- |
| GET | `/capabilities` | 版本、算法后端、动作空间、执行目标和适配边界 |
| POST | `/sessions` | 创建会话，返回 id |
| GET | `/sessions`、`/sessions/{id}` | 配置、episode 状态、转换数量、人工接管比例、奖励标签统计 |
| GET | `/sessions/{id}/observation` | 获取模型状态及会话相机观测，图像保存于本机数据目录 |
| POST | `/sessions/{id}/step` | `{"action":[0,0,0,0,0,0],"kind":"demonstration"}` 执行一个有界模型动作，记录前后观测与实际动作，返回 transition_id |
| GET | `/sessions/{id}/transitions` | 返回最早的最多 100 个转换样本，用于诊断；不是视频流接口 |
| POST | `/sessions/{id}/intervention` | `{"enabled":true,"joint_positions":{六关节弧度目标}}` 接管；`enabled:false` 交回策略 |
| POST | `/sessions/{id}/feedback` | `{"success":true,"transition_id":1}` 标记当前 episode 最新转换的奖励并结束 episode；失败用 false，时间截断另加 `truncated:true` |
| POST | `/sessions/{id}/labels` | `{"reward":0}` 或 `{"reward":1}` 保存当前相机观测的视觉奖励标签，不结束 episode |
| POST | `/sessions/{id}/reset` | `{}` 开启下一个 episode，清除接管；需先停止 actor，不发送归位动作 |
| POST | `/sessions/{id}/stop` | `{}` 停止会话及关联的学习器/执行者/奖励训练任务 |

创建配置示例：

```json
{
  "task": "移动到目标区域",
  "fps": 2,
  "cameras": ["virtual"],
  "roi": {"virtual": [0, 0, 240, 320]},
  "max_joint_step_rad": 0.02,
  "max_episode_steps": 40
}
```

`cameras` 最多两个，接受已发现的 `opencv_<标识>`、virtual、兼容旧配置的 real。可用设备通过 `/api/v1/cameras` 查询。虚拟相机需显式装配并保持 table 运行；包含虚拟相机时 fps≤2，其他会话 fps≤30。ROI 为 `[top,left,height,width]`，处理前验证画面边界，再统一缩放为 64×64 RGB。

动作顺序固定为 shoulder_pan、shoulder_lift、elbow_flex、wrist_flex、wrist_roll、gripper。每维是 [-1,1] 的关节增量，乘以 max_joint_step_rad 得到 rad 增量。每步同时限制 URDF 范围、0.25 rad/s 速度和模型碰撞边界；实际发送节拍也受 fps 限制。回放数据保存实际裁剪后的动作，人工接管样本单独标记。

`kind` 为 demonstration 或 online。先用 step 记录少量人工示教，末步标注 success/failure；再启动学习器和执行者。没有显式成功标注的非终止转换奖励为 0。时间截断与真实成功/失败终止分开保存，SAC 仅对真实终止停止 bootstrap。

接管目标最多有效一秒，需要持续更新。开启接管但没有有效目标时保持位置，不自动恢复策略。接管在下一次动作分发前检查，不是独立急停。stop 返回后不再发起新模型动作，已经接受的模型目标保留。

记录关节来源为 table_display_target，physical 始终为 false。动作后要求收到较新的相机帧，但不构成渲染到位确认、硬件时钟同步或实机反馈。如果动作已经发送但后续图像缺失/状态被外部控制修改，接口会报错，不写入该转换；调用方应读取模型状态，不能直接重试动作请求。

## 学习器、执行者及奖励分类器

| 方法 | 路由 | 请求 |
| --- | --- | --- |
| POST | `/learners` | `{"session_id":"…","device":"cuda","steps":1000,"batch_size":16,"checkpoint_interval":50,"idle_timeout_s":300,"demonstration_session_ids":[]}` |
| POST | `/actors` | `{"session_id":"…","learner_job_id":"…","device":"cpu","steps":40}`；可加 reward_job_id、success_threshold（默认 0.7） |
| POST | `/predictions` | `{"session_id":"…","learner_job_id":"…","device":"cpu"}`；预测一次，返回归一化动作，executed=false |
| POST | `/reward-trainings` | `{"session_id":"…","device":"cpu","steps":1000,"batch_size":16}`；要求会话已有成功和失败两类相机标签 |
| GET | `/jobs`、`/jobs/{id}` | 任务状态、loss、步数、数据量、权重版本、日志或结果 |
| POST | `/jobs/{id}/stop` | `{}` 停止指定后台任务 |

三个启动接口和预测接口返回 202 任务对象，实际工作在后台子进程完成。状态沿用 queued/running/succeeded/failed/cancelled/interrupted。服务退出时关闭任务，异常退出由子进程监测宿主并结束；重启后未完成任务标记 interrupted，不自动恢复。

- 学习器：LeRobot SAC 原生 actor/critic/temperature 损失、Adam 更新与目标网络更新。图像使用原生随机初始化 CNN，可训练，不触发网络下载；状态按 URDF 范围归一化。模型数据没有末端力矩、电流或实机速度输入。
- 回放：在线和离线/人工干预样本同时存在时，各占约一半 batch。可从其他同配置 RL 会话读取示教，要求相机、ROI、动作尺度一致。当前不自动把 ACT 数据集转换成带奖励的 RL 转换。
- 权重：学习器先发布初始策略，再定期原子发布权重文件；执行者读取新版本。训练停止后只有完整文件可读；当前未保存优化器恢复状态，不支持断点续训。
- 奖励：默认由操作者标注，视觉奖励可选。奖励任务训练本项目的小型 CNN 二分类器，输出成功概率；它不是官方预训练奖励模型，质量未经自动验收。执行者预测概率达到 success_threshold 时标注成功并结束 episode。
- 调度：最多三个 RL 后台任务并行，同会话同角色只允许一个；table 同时仅允许一个 RL actor。角色失败会暴露错误，不伪装训练成功。结束 actor 不自动取消 learner，整体停止请调用 session stop。

SQLite、图像、任务状态和权重默认保存在 `core/data/reinforcement_api/`，由现有 Git 忽略规则排除。SAC 后端和任务进程仅在显式请求后初始化，服务启动不加载模型、不启动训练。

## Python 客户端

```python
from xiaoxia_core.reinforcement.client import ReinforcementClient

rl = ReinforcementClient()
session = rl.create_session("移动到目标区域", fps=2, cameras=["virtual"])
sid = session["id"]

# 以下调用会实际改变 table 模型，请在需要时显式调用。
# rl.step(sid, [0.1, 0, 0, 0, 0, 0], kind="demonstration")
# rl.feedback(sid, success=True)
# rl.reset(sid)
# learner = rl.learner(sid, device="cuda", steps=1000)
# actor = rl.actor(sid, learner["id"], steps=40)
# rl.intervene(sid, enabled=True, joint_positions={...完整六轴目标...})
# rl.intervene(sid, enabled=False)
# rl.job(learner["id"])
# rl.stop_session(sid)
```

## 本次检查边界

完成 Python 语法、SAC 后端导入与临时目录中的会话/接管/reset/stop/非法动作契约检查。检查没有模型动作、没有实机访问、没有策略实例化或训练。梯度更新、视觉分类器效果、在线执行与任务成功率未运行验收；不能把 API 完成或导入成功视为训练效果证明。

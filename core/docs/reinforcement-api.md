# 强化学习 HTTP API

Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian

流程参考 [LeRobot HIL-SERL 指南](https://hugging-face.cn/docs/lerobot/hilserl) 和 [0.4.4 版本指南](https://huggingface.co/docs/lerobot/v0.4.4/hilserl)。当前实现是面向 table 的适配：复用 LeRobot 0.4.4 原生 SACPolicy，通过 HTTP 与 SQLite 交换转换数据和权重；人工提供示教与成功/失败反馈，可选本地视觉奖励分类器。它不是官方 gRPC、实机末端位移和 IK 流水线的直接启动器。

服务 `http://127.0.0.1:8766`，统一前缀 `/api/v1/reinforcement`。所有路由要求已有 `Authorization: Bearer <XIAOXIA_MOTION_TOKEN>`；POST 使用 JSON。复用现有 Conda base，不新建环境、不自动下载视觉预训练权重、不上传 Hub、不连接串口。

## 拿取小球

左侧「策略 → 强化学习 · 拿取小球」积木配置同时训练数量（1–16，默认 4）、每个环境训练轮数（1–10000，默认 100）和 CPU/CUDA。绿色运行按钮只启动后台任务，Python 源码保持隐藏。中间顶部的小型半透明面板显示当前分数、最近 100 个已完成回合的平均累计奖励、回合进度和百分比，支持停止任务。开始时没有已完成回合，平均分显示「—」。画面按实际环境数量同台展示各机械臂、小球和独立姿态，视角自动适配；不修改普通模型 API 的显示目标。

训练和 ONNX 仿真将所有环境状态写入轻量 `preview.json`，独立于面板状态刷新。桌面复用一个持久 Tauri Channel 读取预览，约每 80ms 检查新帧；前端逐帧插值显示，不能把插值帧视为额外物理步。网格/材质共享，关节状态独立，不复制环境 1 的动作冒充多个环境。窗口卸载会取消预览子进程。

`POST /ball-trainings` 可选 `warm_start_job_id`：从已结束的抓球训练最近完整权重加载策略，包括已停止或失败但保有完整检查点的任务。这是权重接续，优化器与经验缓存重新初始化，回合数按新任务计算，不是完整断点恢复。初始化时若没有完整权重则明确报错。

`POST /ball-trainings` 请求 `{"num_envs":4,"rounds":100,"device":"cpu","seed":42}`，返回 202 和 `kind=ball_pickup` 的任务对象；同一时刻只允许一项小球训练。每环境各训练 rounds 回合，总回合为 num_envs×rounds。多个 MuJoCo MjData 独立推进，线程池最多 8 个工作线程，批量策略采样并共享 SAC 学习器；不是多份互不相关的模型训练。状态沿用 `/jobs/{id}`，停止沿用 `/jobs/{id}/stop`。MCP 对应 `rl_train_ball`。

当前抓球环境为 `so101_pickup_v2`，添加地面和半径 1.5cm、质量 12g 的自由小球。复用 SO-101 URDF 关节、惯量和视觉网格，仅将固定指与移动指的碰撞网格分别替换为源 STL 的 24 个凸分解，避免整块 STL 凸包填充夹爪凹槽。抓取参考点改到指间有效抓取区 `[0.0071,-0.000218121,-0.092]`（gripper_link 局部坐标，m）。分解是近似模型，24 个凸体的数量上限使最大凹度高于请求阈值；原始 STL 哈希与参数记录在各碰撞目录的 source.json，不能把仿真检查当作硬件接触认证。

状态包含六关节位置、速度、小球位置和相对抓取点位置。每步推进 0.2 秒，每回合最多 100 步；时间截断继续 bootstrap，真正终止不 bootstrap。成功必须同时满足双指各有超过 0.01N 的有效法向接触力、小球不受地面支撑、相对本轮落稳高度抬升至少 5cm，且在物理推进中连续保持至少 1 秒；每 10 个物理步（0.02 秒）检查，接触或抬升条件丢失立即清零保持计时。回合结束后不能再次 advance，防止重复领取成功分。

### 球的位置刷新

每次 reset_episode 独立采样 X∈[0.16,0.23]m、Y∈[-0.05,0.05]m。先清除旧状态和速度，将球放到地面上方，再执行 0.2 秒受控落稳；以实际落稳球高作为本轮抬升基准，同时清空奖励、保持时间和终止状态。球只在回合初始化重置，夹取过程中不绑定球、不传送球。多环境使用 seed+环境编号的独立随机流。

预览携带 episode_index、spawn_position、floor_z、接触力、held_seconds 和分项 reward_terms。换回合时机械臂与小球直接切换到新状态，不沿用上一轮位置做插值；同轮内继续平滑渲染。

### 加分与扣分（pickup_v2）

| 项目 | 规则 |
|---|---|
| 靠近/远离 | `5×(上一步距离−当前距离)`，远离为负 |
| 首次有效夹起 | 双指接触且离开地面，仅本轮首次 +1 |
| 抬升进展 | `10×(本步夹持抬升比例−上步比例)`，5cm 封顶；失去夹持扣回相应进展分 |
| 成功保持 | +50，并结束回合，只能领取一次 |
| 每步时间 | -0.01 |
| 动作消耗 | `-0.002×mean(action²)` |
| 掉球 | 曾有效抬升后失去夹持或落回低处，额外 -3 |
| 越界/跌落异常 | XY 距原点超过 0.6m，或球低于地面 2cm，-10 并结束 |
| 超时 | 第 100 步未成功，额外 -2 |
| 机械臂撞地 | 非固定底座部件地面接触力 `-0.05×min(力,20N)` |

不再按接触次数或静止接触每步加分。分数可以为负，不是成功率；完整配置在任务 reward_config，分项在 reward_terms。新旧奖励不能直接比较。抓取参考点和接触定义均已变化，v1 权重不能作为 v2 的接续或仿真推理模型，必须重新训练；旧文件保留，纯输入 ONNX 推理仍按其自身契约使用。

抓球控制使用 MuJoCo 原生位置执行器逐物理步计算 P 项，每 10 个物理步更新受速度限制的设定点和偏置补偿，执行器力矩限制保持生效；物理步长仍为 0.002 秒。这样减少 Python 多环境控制循环开销，奖励及成功判定不变。Windows 原子 JSON 替换使用独立临时文件及有限占用重试，避免界面读取状态时的瞬时文件占用中断训练。

任务状态提供 `num_envs`、`rounds`、`completed_episodes`、`total_episodes`、`env_rounds`、`progress`（0–1）、`score`、`current_score`、`successes`、`success_rate`、`transitions`、`updates`、loss 和 `snapshot`。抓球环境使用仿真真值状态，不要求相机或人工奖励标签。模型和分数属于仿真，未证明真机抓取或策略收敛；MuJoCo 网格接触近似和实际硬件存在差异。

## ONNX 导出与推理

新抓球训练完成后自动导出 `policy.onnx` 和 `policy.onnx.json`，任务只有在 ONNX 导出、模型结构检查及 PyTorch/Runtime 数值对齐检查成功后才标记 succeeded；保留 `.pt` 权重。已有训练可单独导出，不需要重新训练。此功能适用于 18 维抓球 SAC 模型，不适用于 ACT 或含视觉输入的 HIL 会话策略。

| 方法 | 路由 | 请求 |
|---|---|---|
| POST | `/onnx-exports` | `{"training_job_id":"训练任务ID或latest"}`，返回后台导出任务 |
| POST | `/onnx-predictions` | `{"model_job_id":"模型任务ID或latest","states":[[18个数值]]}`，返回 `actions:[batch,6]`，不发送动作 |
| POST | `/onnx-rollouts` | `{"model_job_id":"模型任务ID或latest","rounds":1,"seed":42}`，返回后台 ONNX Runtime 抓球仿真任务，不更新权重 |

导出/运行任务继续使用 `/jobs/{id}` 查询和停止。`model_job_id` 接受已成功并有 ONNX 文件的新训练任务，或已完成的独立导出任务；不接受任意文件路径。`latest` 在导出时选最近完成的抓球训练，在推理时选最近已完成且具备 ONNX 文件的可用模型。若没有可用模型则明确报错。

左侧策略增加「导出抓球模型 ONNX」和「ONNX 推理 · 拿取小球」积木，默认模型任务为 latest。旧模型先运行导出积木，等任务成功后再运行推理积木；新模型训练后可直接推理。推理过程复用中间顶部面板展示实际分数、回合和状态。

输入 `state` 为 float32 `[batch,18]`，API batch 范围 1–64。顺序固定为六关节位置（rad）、六关节速度（rad/s）、小球世界位置 XYZ（m）、小球相对夹爪抓取点的位置 XYZ（m）。各六轴顺序均为 shoulder_pan、shoulder_lift、elbow_flex、wrist_flex、wrist_roll、gripper。与训练相同，输入使用原始仿真单位，不额外归一化；不能拿六个模型目标角度冒充完整观测。

输出 `action` 为 float32 `[batch,6]`，范围 [-1,1]；乘以 0.08 得到关节增量（rad），仿真环境继续应用 URDF 范围、速度和力矩限制。模型导出确定性动作 `tanh(actor_mean)`，不包含训练时的随机探索采样、Critic 或优化器。ONNX Runtime 推理模块不导入 PyTorch/LeRobot；MuJoCo 仿真执行仍由现有独立环境负责，所有接口均不操作实机。

采用 ONNX opset 17、动态 batch、CPUExecutionProvider，并随文件保存 SHA-256、输入输出契约、关节顺序和导出数值误差。导出机制参考 [PyTorch ONNX 文档](https://docs.pytorch.org/docs/stable/onnx)，运行方式参考 [ONNX Runtime Python 文档](https://onnxruntime.ai/docs/api/python/api_summary.html)。复用 Conda base，新增 onnx/onnxruntime 依赖；不创建新环境。

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

## 检查记录与边界

初始 API 检查覆盖 Python 语法、SAC 后端导入与临时目录中的会话/接管/reset/stop/非法动作契约，没有实机访问。视觉分类器效果、HIL 在线执行与真机任务成功率仍未验收。

2026-11-02 通过有限 MCP 调试接口完成一次积木训练闭环：`blocks_catalog → blocks_export → blocks_import（临时空工作区）→ blocks_create → blocks_run → rl_get_job → blocks_import（恢复）→ blocks_export（比对）`。没有直接调用训练启动 API，也没有手写训练程序替代积木生成代码。工作区只放置 `table_policy_rl_ball`，字段为 `NUM_ENVS=1, ROUNDS=1, DEVICE=cpu`。

- 任务 `27cdc74ec4534aa7bd7677affd69fb52`：succeeded，完成 1/1 回合，进度 100%，从任务启动到完成约 39 秒。
- 采集 100 个转换样本，完成 37 次 SAC 参数更新，生成 `policy-00000037.pt`；最终累计奖励/平均分均为 1.3075079019860936，界面显示 1.31。
- 本轮抓取成功 0 次，`task_success_validated=false`。本次证明积木启动、经验采集、参数更新、进度展示和权重保存闭环可用，不证明策略已学会抓球或收敛。
- WebView 只读检查确认面板位于三维区顶部 16px、水平居中、宽 360px，显示训练完成、1/1、100% 与实际分数。原工作区恢复后完整快照比对一致，未执行原有机械臂位置积木。

本机详细回执保存在 Git 忽略的 `core/data/runtime/ball-block-check.json`，工作区备份为同目录 `ball-block-workspace-backup.json`；面板完成态记录为 `ball-panel-final.json`。没有构建桌面、发送真实 LLM 请求或连接实机。

同日用「导出抓球模型 ONNX」积木导出上述训练权重，任务 `39ee5bb78bfe495f8c8341669a41423f` succeeded，生成 151200 字节的 policy.onnx 和伴随契约文件。导出检查的 PyTorch/ONNX Runtime 最大绝对误差为 2.682209014892578e-7；通过 MCP 对两条 18 维状态做只读推理，相同输入的重复输出完全一致。随后「ONNX 推理 · 拿取小球」积木启动任务 `1215a17083ab4a1ea6543d0383419fc1`，仅使用 ONNX Runtime 完成 1/1 回合、100 个物理转换，得分 -0.4069328814359693，成功 0 次，training=false。未重新训练，原工作区快照恢复一致。此检查覆盖旧权重独立导出与运行；新训练自动导出复用同一导出器，本次没有为检查自动导出另行训练。

首次导出积木的运行回执超过 8 秒进入 unknown，但后台任务已创建；通过原 command_id 查询到迟到的 succeeded 回执后继续，没有重发导出。原始失败记录和恢复后的完成记录分别在 `core/data/runtime/onnx-block-check.json`、`onnx-recovered-check.json`，不能把首次 unknown 误当作未执行。

后续扩量训练及多臂渲染检查：旧任务 `6d0e28c4709b4b1aa91020adf3fd073b` 在完成 216/800 回合、2730 次更新后遇到 Windows 状态文件替换占用而失败。增加原子替换有限重试后，新任务 `63b25f1482e447debb6a202d122c31a8` 从最近完整策略权重接续，重新建立优化器与经验缓存，以 8 个环境各 100 轮完成 800 回合、80000 个转换、9993 次 SAC 更新。最近 100 回合平均奖励 9.1884426768836，训练成功抓取 0 次。ONNX 自动导出成功，最大绝对误差 4.470348358154297e-7。

使用独立种子 20261102 的 ONNX 评估任务 `ff0f6c49dfa945c5aa691f1697a90831` 完成 20 回合，平均奖励 10.583112833079813，成功 0/20；因此不能将该模型标为“好模型”或已掌握抓取。详细记录在 `core/data/runtime/extended-multi-training.json`。训练期间实际预览包含 8 个环境、8 组不同关节姿态，WebView 截图确认同台显示 8 台机械臂和独立小球；TypeScript 检查通过，没有构建桌面或实机动作。

### v2 物理、重置及奖励检查

使用 `core/scripts/check_ball_pickup_physics.py --seeds 42 43 44 45 46` 的参考 IK 控制，在 5 个不同出生位置均完成双指夹持、抬升和保持，抬升 8.04–8.08cm，连续有效保持 1.10–1.18 秒；成功时双指法向力约 0.85–0.89N，球无地面支撑。每次松手后球都靠重力落回地面，无焊接、吸附或抓取过程中的位置传送。随后各执行 3 次重置，位置均刷新、分数与保持时间清零、残余速度约 3.2e-9m/s。证据摘要见 [物理检查记录](pickup-physics-v2.json)。这是参考控制的物理可行性检查，不是学习策略成功率。

奖励分项检查：静止 -0.01，靠近 5cm 为 +0.24，远离 5cm 为 -0.26，静止夹持不持续加分；半程抬升增加 +4.99，随后掉球扣 -8.01（含进展回退和掉球惩罚）。超时 -2.01、越界失败 -10.01，均含本步时间成本。未继续启动训练，先确认 v2 的物理、球位置刷新及计分基础。

复现时在现有 base 中设置 PYTHONPATH=core/src，然后运行上述脚本；运行目录为仓库根，输出可用 --output 指定。已提交的凸分解可直接用于运行，普通训练不需要 CoACD；只有重新生成碰撞资产时才需要可选 physics-tools 依赖，并运行 core/scripts/prepare_gripper_collisions.py。未进行桌面构建或实机动作。


### v3 相机、示教和随机观测噪声（2026-11-02）

现有 `ball-trainings` / 积木训练入口默认采用 `so101_pickup_v3_vision`，无需新增积木字段。腕部相机固定在 gripper_link，与界面装配坐标及 60° 视场一致；每个环境使用自身 MuJoCo 状态渲染 64×64 RGB，不依赖 WebView 截图或相机预览是否显示。策略接收图像和原 18 维状态，仍包含仿真球位置等特权信息，因此不是纯视觉策略，也不代表已支持真机迁移。

训练开始先在随机球位置采集 8 轮成功 IK 示教（最多尝试 24 轮，未达到则明确失败），只有满足原双指接触、抬升和持续保持判定的轨迹被保留。示教存入任务目录 demonstrations.npz，包含前后状态、前后 RGB、动作、奖励、终止标记；先做 200 次行为克隆，再启动 SAC。每个 64 样本训练批次包含 48 个在线样本和 16 个示教样本，并持续更新示教行为克隆损失。在线视觉回放上限 5000 条，RGB 用 uint8 存储。示教次数单独上报，不计入策略训练成功率。

训练观测加入独立、可复现的随机噪声：关节位置标准差 0.002rad、速度标准差 0.005、位置标准差 1mm；RGB 高斯噪声标准差 0.01（按 [0,1]）、亮度倍率均匀分布 [0.9,1.1]。不修改真实物理状态、奖励、接触判定，也未随机化质量或摩擦。ONNX 仿真评估默认使用干净观测。

视觉 ONNX 包含 state=[batch,18] 与 wrist=[batch,3,64,64] 两个 float32 输入，图像为 RGB、CHW、范围 [0,1]。HTTP onnx-predictions / Python predict_onnx / MCP rl_predict_onnx 同时接受 states 和 images；视觉策略缺少图像会明确报错。旧无图像 ONNX 仍可单独预测，但旧环境模型不能在 v3 环境中接续训练或作为新版有效 rollout。

有限检查：种子 42 的一条示教取得 65 个转换并持续有效抬升约 1.1 秒；四样本行为克隆、一次视觉 SAC 更新、ONNX 导出和双输入推理通过，最大绝对误差约 1.28e-7。未运行完整新训练或成功率评估，未构建桌面、未操作实机。


### v4 红球发现与空抓奖励（2026-11-02）

当前 ball-trainings 默认环境为 so101_pickup_v4_visual_reward，奖励版本 pickup_v3_visual；保留 v3 图像、示教和噪声。每次动作后从腕部干净 RGB 判断红球可见（至少 6 像素满足 R>40、R>1.4G、R>1.4B），首次可见加 1 分，每回合最多一次，避免反复丢失/重新发现刷分。发现不代表抓取成功。训练与示教回放均包含此奖励，ONNX rollout 计分一致。

夹爪闭合动作小于 -0.02 且双指都未与红球产生超过 0.01N 的接触时，扣 0.2×闭合指令幅度，单步最多扣 0.2；张开、静止或已有任一指接触红球不扣此项。原先抬升、成功、掉落及时间惩罚保留。新奖励不复用旧回放或旧模型，旧任务停止后从新示教重新训练。


### 扩量训练与独立成功验收（2026-11-02）

ball-trainings 增加 demonstration_episodes（8–256，默认8）、pretraining_updates（200–50000，默认200）、stop_on_success（布尔，默认false）。抓球 SAC 的标准差范围限制为 0.01–0.1，减少示教后的大幅随机动作；接近/下降阶段的定时静止帧不作为示教动作，避免将阶段等待误学成永久停住。

stop_on_success 开启后，每1000次预训练更新及每500次在线更新，在独立球位置用确定性学习 Actor 评估5轮；至少成功3轮才提前结束并导出。评估不调用 IK/示教控制器，结果写入 evaluation.json，示教成功、在线成功、评估成功分别统计。

`core/scripts/train_ball_until_success.py` 使用现有 base 环境和 CUDA 启动持续扩量流程：首批8环境×1000轮、64轮示教、5000次预训练；后续批次逐步增加示教与更新量，接续上一批模型权重但重新建立优化器/回放。每批结束独立执行20轮 ONNX 推理，至少成功1轮才结束流程；低于16/20时明确 robust_grasp_validated=false，不宣称稳定抓取。进程故障明确报告 failed，不悄悄重试掩盖故障。报告为 core/data/runtime/pickup-campaign.json；任务 ID 可通过原 stop 接口停止。

抓球观测在进入网络时按量纲缩放：关节位置×0.5、速度×0.1、球世界坐标×5、球与夹爪差向量×20。原始采样/示教文件/HTTP 输入仍使用弧度和米，ONNX 将该缩放固化在图中并在 manifest 记录 state_scale，避免位置差特征被数值更大的关节角淹没。

扩量流程支持 corrective_demonstrations（默认false，持续训练脚本启用）：独立检查未通过时，采集模型偏离示教轨迹后的专家纠正标签，并用于后续行为克隆。纠正采集混合执行70%专家动作与30%模型动作，只存观测/专家动作标签，不作为 SAC 转换，也不计作独立策略成功。最终 ONNX 推理仍完全由学习模型执行。demonstration_job_id 可复用同环境且成功数量足够的示教归档；不自动复用旧回放。预训练每1000次更新保存权重，预览文件暂时被Windows占用只丢帧，不终止训练。


### 已取得学习模型抓取成功（2026-11-02）

扩量任务 31b642699f764b3291fd0694cd84868e 复用64轮成功示教，共2966条有效转换；1000次GPU行为克隆更新后，独立学习Actor验证达到3/5成功，按规则提前导出，尚未进入本轮在线SAC（updates=0），不能写成已完成8000轮强化学习。实际示教样本数见 [模型验收记录](pickup-trained-model.json)。

ONNX Runtime任务 aa953077234d4036be66436b183c8967 使用新种子20261104完成20轮，成功7轮（35%），由导出的网络独立推理，无IK或专家动作介入。成功仍要求双指力接触、无地面支撑、至少抬升5cm并持续1秒；学习Actor检查中成功保持1.08–1.10秒。ONNX最大数值误差4.17e-7。已经具备抓取能力，但稳定抓取尚未验收（robust_grasp_validated=false）。模型位于对应任务目录policy.onnx，体积较大不纳入Git，报告和权重保留在本机。未进行桌面构建或实机操作。


### 当前策略 v5（2026-11-02）

旧版“出现一次成功即可停止”已废弃。当前采用阶段条件SAC、三档课程、困难样本与示教约束、至少2000次在线更新，以及100随机＋100噪声＋35边界网格全部成功的验收。详见[抓球策略v5](pickup-strategy.md)。新版状态为31维；旧版模型与数据禁止混入新版训练。当前实现验证不代表已取得100%抓取率。


### 当前优化 v6（2026-11-02）

当前环境so101_pickup_v6_stable_sac，针对v5在7cm处悬停、在线更新破坏示教的表现，增加下降/方向/首次接触奖励、Critic预热、强示教锚定和小步Actor更新。连续六次验证零成功或每批10000次在线更新仍未合格则扩量进入下一批，235/235最终验收不变。详见[当前策略](pickup-strategy.md)。


### 积木模型目录与一次推理检查（2026-11-02）

GET /api/v1/reinforcement/models 返回已完成训练/导出的模型目录、环境兼容性和ONNX是否存在。策略分类增加“刷新模型”；ONNX导出/推理积木的模型字段改为动态下拉，推理只列同环境且已导出的模型。latest在服务端也过滤环境版本；未知或失效的已选ID保留为不可用提示，防止快照加载静默换模型。当前目录用“未验收”标明尚未具备235/235证据的候选，不将任务完成误当作模型合格。

通过实际WebView命令桥执行catalog→export备份→import临时工作区→create(table_policy_onnx_run，MODEL_ID=6afb815b26a94e8d8ff4193d6c8b403a，ROUNDS=1)→run→import恢复→export比对。仅由积木生成Python启动推理，没有直接调用rollout接口替代积木执行。任务5d3ed7a6bb174ad58a63151545391452成功完成1轮，成功抓取1次，工作区恢复一致；这不代表235/235或全范围100%验收通过。证据见[积木推理回执](onnx-block-inference.json)。TypeScript检查通过，未构建桌面，未连接实机。


### 推理动画节奏（2026-11-02）

onnx-rollouts和Python rollout_onnx新增playback_speed，默认1.0倍速（正常速度）；每步按真实推进的MuJoCo物理时间等待，再发布一帧预览，仅在下一轮存在时等待0.3秒再重置进入下一轮。模型输入、动作、物理步长和奖励不变；计算变慢时不靠连续跳帧追赶。可用0.1–4倍速；0表示快速批量评估，持续训练脚本的235轮验收明确传0，避免动画减速影响验收速度。积木无需修改字段，默认使用正常速度。

通过同一积木接口重新运行1轮：任务c0c7f8a5ae5d416e897c0c0b36a94adc，45个动作、0.5倍速，从任务开始到结束约19.98秒，成功抓取1次。此项验证播放节奏与单轮结果，不代表全工作区验收通过。


### 推理相机显示（2026-11-02）

ONNX推理自动显示固定腕部相机与支架，无需额外装配相机积木。推理预览流附带kind=ball_onnx_rollout及camera_frame，PNG图像直接来自该动作所用的MuJoCo腕部RGB观测（保留原始像素，包括启用时的观测噪声），并记录输入时刻的simulation_time；画面是动作前输入，主场景展示该动作后的姿态。右下角“腕部相机·推理输入”不再使用Three.js另行渲染的画面代替。

普通虚拟相机积木仍按原设置显示；关闭推理面板后恢复手动相机配置。相机装配坐标由CameraPreset共享。画面仅通过已有本机预览通道传递，不新增外部服务。

任务8ae8166f7629401c930521cc8dd7b54b通过积木执行1轮半速ONNX推理，成功抓取1次，工作区恢复一致。WebView检查确认相机预览可见、source=policy_input、PNG自然尺寸64×64；原生截图确认模型上的相机及支架、输入画面和红球可见。TypeScript检查通过，未构建桌面、未操作实机。


### ONNX 推理暂停与继续

推理进度面板在任务运行时显示“暂停”和“停止”，暂停确认后切换为“继续”。暂停保留当前回合、仿真状态和相机输入，继续后从当前位置执行；已结束任务仅显示“关闭”。默认仍按正常速度播放，回合间等待 0.3 秒。

- `POST /api/v1/reinforcement/jobs/{job_id}/pause`，请求体 `{}`。
- `POST /api/v1/reinforcement/jobs/{job_id}/resume`，请求体 `{}`。
- 只接受未结束的 `ball_onnx_rollout` 任务。响应 `pause_requested` 表示已提交意图；查询任务中的 `paused` 和 `phase=paused` 表示执行进程确认停住。暂停期间任务仍为 `running`，保留资源占用，也可以停止。
- 桌面桥动作：`reinforcement_pause` / `reinforcement_resume`，均传入 `job_id`。

2026-11-02 实测通过积木启动两回合推理，在执行进程确认暂停后，相隔 0.7 秒的预览文件字节完全一致；继续后预览重新变化。结果见 `inference-pause.json`。


2026-11-02 暂停响应优化：前端点击当帧冻结机械臂插值和相机输入，恢复经后台确认后再解除冻结；控制桥绕过 LLM/会话初始化并主动短轮询确认，避免等待面板的 1.5 秒常规轮询。新推理进程在物理子步检查暂停，等待和恢复检查间隔降至 5 毫秒（检查间隔并非端到端实时性保证）。HTTP 控制端增加最多 0.4 秒的确认等待，下一次服务启动生效。

现有 WebView 对已暂停任务重复发送暂停请求实测往返约 365 毫秒，仅代表幂等请求通路，不代表运行到停住的延迟。当前用户的五回合任务保持暂停，未重启服务或执行进程；新物理子步检查须下次推理任务生效。TypeScript 与 Python 语法检查通过，未完整构建。

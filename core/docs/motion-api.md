# 运动路由 API

core 主动向控制服务的机器人路由发送指令。当前接收目标是 table 中的机械臂模型，robot_id 为 `table`。已提供本机 HTTP 服务和 table 模型订阅接口；界面布局不变，不连接实机。通用处理器仍可用于独立控制服务。

| 方法 | 路由 | 作用 |
|---|---|---|
| GET | `/api/v1/robots/{robot_id}/state` | 当前六轴位置，单位 rad |
| POST | `/api/v1/robots/{robot_id}/motions` | 发送六轴绝对目标 |

请求必须携带 `Authorization: Bearer <token>`，使用 HTTPS 或受信的本机网络。宿主 HTTP 服务应限制请求体为 16 KiB，禁用公开跨域访问，不记录令牌，并将解析后的 JSON 传给 `MotionRouteService.handle`。该处理器不提供网络监听、设备连接或自动使能端点。

```json
{
  "request_id": "12345678-1234-4234-8234-123456789abc",
  "expires_at_ms": 1793491200200,
  "unit": "rad",
  "joint_positions": {
    "shoulder_pan": 0.0,
    "shoulder_lift": 0.0,
    "elbow_flex": 0.0,
    "wrist_flex": 0.0,
    "wrist_roll": 0.0,
    "gripper": 0.9
  }
}
```

时间字段为 Unix 毫秒，示例时间必须替换；客户端和接收端需要时钟同步。接收端仅接受未来 1 秒内的截止时间，客户端默认 200 ms。必须完整提供六轴，拒绝非有限值及越界目标；不将限位内目标解释为已通过碰撞检测。

发送成功返回 HTTP 202：

```json
{"request_id":"12345678-1234-4234-8234-123456789abc","robot_id":"table","status":"accepted"}
```

`accepted` 只说明适配器完成发送，不表示到位。GET state 返回 `robot_id`、`unit`、`joint_positions`。401 为鉴权失败，404 为路由或设备不存在，409 为过期或请求 ID 冲突，422 为参数或限位错误，429 为容量不足，503 为设备不可用或执行结果未知。

同一 ID 在有效期内只发送一次，重复请求返回先前回执，修改内容返回 409。该去重仅在当前服务进程内有效；跨服务重启不得重放动作。超时可能发生在远端已经发送之后，因此客户端不自动重试，应先查询设备状态。控制服务必须串行持有设备；不可同时运行 CLI 控制同一串口。

## core 调用

```python
from pathlib import Path
from xiaoxia_core.communication.motion_routes import MotionRouteClient
from xiaoxia_core.contracts import Action
from xiaoxia_core.safety import JointLimits

limits = JointLimits.from_urdf(Path("../table/public/robots/so101/so101_new_calib.urdf"))
with MotionRouteClient("http://127.0.0.1:8766", "table", limits,
                       token=__import__("os").environ["XIAOXIA_MOTION_TOKEN"]) as robot:
    observation = robot.read_observation()
    robot.send_action(Action(dict(observation.joint_positions)))
```

## 服务集成

宿主创建 `MotionRouteService(token=...)`，通过 `register("follower", transport, limits)` 注册已有适配器，将 HTTP 请求映射至 `handle(method, path, authorization, body)` 并返回其状态码及 JSON。实机应注册使用实测校准范围的 SOArmTransport，并在本地显式完成身份确认、连接和安全使能。路由不会跳过这些步骤。

保持连接和失联保护属于宿主控制循环职责。HTTP 客户端 disconnect 只关闭客户端逻辑状态，不代表解除设备力矩；现有 SO 适配器发送超时检查不能替代独立硬件看门狗。当前 COM17 校准问题仍未解决，不能通过本 API 绕过。


## 启动 table 模型 API

在当前工作树的 core 目录执行（沿用 Conda base）：

```powershell
$env:PYTHONPATH = "$PWD/src"
$env:XIAOXIA_MOTION_TOKEN = "替换成自己的随机令牌"
& C:\Users\30470\Anaconda3\python.exe -m xiaoxia_core.communication.model_server
```

随后按 table 原有方式启动桌面。core 客户端使用相同令牌和 robot_id `table` 发送动作。服务仅监听 `127.0.0.1:8766`；显示状态允许本机匿名 GET，POST 始终鉴权。table 每约 33 ms 读取目标，失败后间隔 1 秒重连；卸载时取消请求。仅允许开发源和 Tauri 源读取跨域响应。

这里 GET state 的 `source=display_target`、`physical=false`，表示服务保存的显示目标，不是实时渲染角度或实机反馈。table 逐帧按最高 0.25 rad/s 追踪目标，URDF 未加载或目标不合法时不更新。API 返回 accepted 不能作为画面到位确认。模型使用 table 自带 SO101 URDF 限位，不能直接套用 SO100 训练数据；若要接入 SO100 推理，需要另外完成模型与坐标映射。

本次仅进行 Python 语法和差异检查，未构建、启动服务、运行桌面或发送实机指令。


虚拟相机装配：POST `/api/v1/robots/table/camera`，Bearer 鉴权，JSON 为 `{parent_link, position:[x,y,z], rotation:[roll,pitch,yaw], fov}`，分别使用米、弧度、角度。校验连杆存在、三维向量有限及范围，返回 202 和当前配置；GET state 增加 camera 字段。配置可附加布尔字段 visible；只有 visible=true 才显示相机、视锥和虚拟画面，缺省为 false。该配置不代表渲染到位或真实图像采集。

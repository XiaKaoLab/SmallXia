# 运动路由 API

core 主动向控制服务的机器人路由发送指令。页面路由与设备控制路由独立；本次未修改 table。接收端提供框架无关处理器，尚未启动 HTTP 服务，也未接入实机。

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
    "shoulder_lift": 1.75,
    "elbow_flex": -1.57,
    "wrist_flex": -0.65,
    "wrist_roll": 0.0,
    "gripper": 0.9
  }
}
```

时间字段为 Unix 毫秒，示例时间必须替换；客户端和接收端需要时钟同步。接收端仅接受未来 1 秒内的截止时间，客户端默认 200 ms。必须完整提供六轴，拒绝非有限值及越界目标；不将限位内目标解释为已通过碰撞检测。

发送成功返回 HTTP 202：

```json
{"request_id":"12345678-1234-4234-8234-123456789abc","robot_id":"follower","status":"accepted"}
```

`accepted` 只说明适配器完成发送，不表示到位。GET state 返回 `robot_id`、`unit`、`joint_positions`。401 为鉴权失败，404 为路由或设备不存在，409 为过期或请求 ID 冲突，422 为参数或限位错误，429 为容量不足，503 为设备不可用或执行结果未知。

同一 ID 在有效期内只发送一次，重复请求返回先前回执，修改内容返回 409。该去重仅在当前服务进程内有效；跨服务重启不得重放动作。超时可能发生在远端已经发送之后，因此客户端不自动重试，应先查询设备状态。控制服务必须串行持有设备；不可同时运行 CLI 控制同一串口。

## core 调用

```python
from pathlib import Path
from xiaoxia_core.communication.motion_routes import MotionRouteClient
from xiaoxia_core.contracts import Action
from xiaoxia_core.safety import JointLimits

limits = JointLimits.from_urdf(Path("assets/so100/so100.urdf"))
with MotionRouteClient("http://127.0.0.1:8766", "follower", limits,
                       token="从环境变量读取的令牌") as robot:
    observation = robot.read_observation()
    robot.send_action(Action(dict(observation.joint_positions)))
```

## 服务集成

宿主创建 `MotionRouteService(token=...)`，通过 `register("follower", transport, limits)` 注册已有适配器，将 HTTP 请求映射至 `handle(method, path, authorization, body)` 并返回其状态码及 JSON。实机应注册使用实测校准范围的 SOArmTransport，并在本地显式完成身份确认、连接和安全使能。路由不会跳过这些步骤。

保持连接和失联保护属于宿主控制循环职责。HTTP 客户端 disconnect 只关闭客户端逻辑状态，不代表解除设备力矩；现有 SO 适配器发送超时检查不能替代独立硬件看门狗。当前 COM17 校准问题仍未解决，不能通过本 API 绕过。

# Sim2Real 一期：器灵关节动作

Created on 2026-11-03; Updated on 2026-11-03  
@author: https://github.com/Linmoqian

器灵可绑定仿真或指定 COM 口。左侧「器灵」新增「Sim2Real 预检」；载入真机时显示配置和「启用运动」选项，默认只读。可以依次拼接预检、载入和发送消息。

预检只检查文件和现有控制会话，不打开串口，不写电机、不使能力矩。需要官方校准、已确认的六轴编码器零点及方向、匹配的串口与 URDF、最高 0.15 rad/s 的配置。显示对齐配置不能替代运动坐标验证。

显式启用后复用硬件控制连接，连接时检查 EEPROM 校准与电机模式。每条消息最多尝试一次六轴目标，各轴相对新鲜实测位置最多变化 10°；必须通过关节限位和碰撞检查。目标单位为 rad；到位以实际反馈判断，超时停止，不自动重试。程序保持控制心跳，停止或失联由现有释放机制处理。界面只用新鲜真机反馈更新跟随模型，并标记来源。

API 均为 POST，沿用现有服务鉴权：

- `/api/v1/sim2real/checks`：`port`、`profile`，返回坐标预检及阻塞原因。
- `/api/v1/sim2real/state`：相同参数，返回实测来源、关节状态和预检。
- `/api/v1/sim2real/motions`：额外传入 `enable_motion: true`、`unit: "rad"` 和完整六轴 `joint_positions`；接收不代表到位。

2026-11-03 验证：通过实际积木运行完成 COM17 预检、只读载入及器灵查询。官方校准存在，但控制映射的六轴 zero_tick、direction 缺失且 verified=false，因此正确阻止运动。本轮没有打开电机控制连接或执行实机动作；实机坐标、限速和到位验证尚未完成。本阶段不包含抓取策略的 Sim2Real。


## 简化坐标标定 API

基地址 `/api/v1/sim2real/calibrations`，沿用服务鉴权。只测量控制坐标，不写电机 EEPROM、不改动力矩。操作者仍需确认姿态与正方向；接口不会从极限中值猜测零点。

| 请求 | 参数 | 用途 |
| --- | --- | --- |
| POST 基地址 | `port: "COM17", profile: "so100.local.yaml"` | 创建会话，返回 id、zero 步骤与六轴零位参考 |
| GET `/{id}` | 无 | 获取当前步骤 |
| POST `/{id}/sample` | 零点时 `pose_confirmed: true`；方向时 `positive_direction_confirmed: true` | 自动读12帧、取中值并计算；成功后推进下一轴 |
| POST `/{id}/save` | `confirmed: true` | 完成六轴后校验并原子保存，保留旧映射备份 |
| POST `/{id}/cancel` | `{}` | 取消未保存会话，不改动已有映射 |

界面只需按 `stage` 显示操作，使用 `reference_rad` 展示参考模型，以 `joint` 突出当前轴，显示 `instruction`。zero → direction（六轴自动推进）→ review → saved。保存返回 `close_panel: true`。每次方向采样从本轴零位向仿真正方向移动约5至20度；reference_rad 显示10度参考，其他轴为零。返回的 reference_rad 是显示数据，接口不会发送到真机。

轻微抖动自动滤波；超过24刻度波动则保留原步骤，调用方稍后重采。接口同步采样，轮询请求不能并发。每次释放串口；配置/官方校准改变、EEPROM不匹配、力矩开启或已有控制会话时拒绝采样。会话30分钟无进展失效，禁止直接跳过步骤保存。缺少官方校准时应转入现有官方校准流程。

2026-11-04 联调：实际 HTTP 创建/查询/取消成功；缺少姿态确认、提前保存和取消后采样返回422。COM17 只读12帧采样成功，从 zero 推进 direction；诊断会话随后取消，原控制映射未改变、未写电机。发现配置引用旧官方校准，已改为与设备 EEPROM 完全匹配的现有文件 xiaoxia_COM17_cc6356e7d58b.json。

隔离临时目录用明确标注的软件输入跑通六轴正负方向、review、save、备份及 close_panel；不代表真实方向已确认。真实六轴方向和保存尚未完成。API 尚未接入前端专用面板。首次采样会加载电机库，调用方建议使用40秒超时；超时后先查询会话状态，勿盲目重复 sample。

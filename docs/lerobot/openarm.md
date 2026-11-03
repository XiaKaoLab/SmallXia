# 来源

https://hugging-face.cn/docs/lerobot/openarm

# OpenArm

[OpenArm](https://openarm.dev) 是一款开源的 7 自由度拟人机械臂，专为物理 AI 研究与部署而设计。

如需获取 OpenArm（成品或 DIY 套件）并加入全球社区，请访问 [openarm.dev](https://openarm.dev) 浏览全球经过验证的认证制造商。

## 有何独特之处？

* **人机尺度设计**：OpenArm 采用拟人比例，模拟身高约 160-165 厘米的人体。这在实用臂展与易于控制的惯性之间达到了最佳平衡，确保操作既安全又灵敏。
* **安全优先架构**：采用 QDD（准直驱）可回溯电机和高顺应性设计，OpenArm 在保证安全人机交互的同时，维持了实际任务所需的有效载荷能力（峰值 6.0kg / 额定 4.1kg）。
* **持久耐用**：关键结构部件采用铝合金和不锈钢制造，确保在重复数据采集和持续科研使用中的坚固表现。
* **完全开放与可构建**：从 CNC 加工件、3D 打印外壳到电气布线，所有组件均设计为可由独立研究人员和实验室购买或制造，并提供完整的制造数据。
* **实用且经济**：双臂系统全套价格仅为 6,500 美元，以传统人形机器人成本的一小部分提供科研级性能。

## 平台要求

> \*\*仅限 Linux\*\*：OpenArm 目前仅支持 Linux 系统。CAN 总线 USB 适配器没有 macOS 驱动程序，也尚未在 Windows 上进行测试。

## 安全指南

操作 OpenArm 前，请阅读[官方安全指南](https://docs.openarm.dev/getting-started/safety-guide)。要点如下：

* **稳固安装**：使用螺钉或夹具将机械臂固定在平整、稳定的表面上
* **安全距离**：操作期间请确保身体部位及其他物体远离机械臂的运动范围
* **防护装备**：务必佩戴护目镜；根据需要使用其他个人防护装备 (PPE)
* **载荷限制**：请勿超过规定的载荷限制（每臂峰值 6.0kg / 额定 4.1kg）
* **紧急停止**：熟悉紧急停止装置的位置及操作方法
* **定期检查**：检查是否存在螺钉松动、机械限位损坏、异常噪音及电线损伤

## 硬件设置

请遵循官方 [OpenArm 硬件文档](https://docs.openarm.dev)进行：

* 材料清单与采购
* 3D 打印说明
* 机械组装
* 电气布线

硬件存储库位于 [github.com/enactic/openarm](https://github.com/enactic/openarm)。

## CAN 总线设置

OpenArm 通过 CAN 总线与 Damiao 电机通信。将 CAN 总线 USB 适配器插入 Linux 电脑后，请参考[《Damiao 电机与 CAN 总线指南》](damiao.md)配置接口。

快速设置

```
# Setup CAN interfaces
lerobot-setup-can --mode=setup --interfaces=can0,can1

# Test motor communication
lerobot-setup-can --mode=test --interfaces=can0,can1
```

## 安装 LeRobot 🤗

请遵循我们的[安装指南](installation.md)，然后安装 Damiao 电机支持库。

```
pip install -e ".[damiao]"
```

## 用法

### 从动臂（机器人）

命令

API 示例

```
lerobot-calibrate \
    --robot.type=openarm_follower \
    --robot.port=can0 \
    --robot.side=right \
    --robot.id=my_openarm_follower
```

### 主动臂（遥操作）

主动臂用于遥操作——通过手动移动主动臂来控制从动臂。

命令

API 示例

```
lerobot-calibrate \
    --teleop.type=openarm_leader \
    --teleop.port=can1 \
    --teleop.id=my_openarm_leader
```

### 遥操作

使用主动-从动控制进行 OpenArm 遥操作：

```
lerobot-teleoperate \
    --robot.type=openarm_follower \
    --robot.port=can0 \
    --robot.side=right \
    --robot.id=my_follower \
    --teleop.type=openarm_leader \
    --teleop.port=can1 \
    --teleop.id=my_leader
```

### 双臂遥操作

使用两组主动臂和从动臂进行双臂 OpenArm 遥操作：

```
lerobot-teleoperate \
    --robot.type=bi_openarm_follower \
    --robot.left_arm_config.port=can0 \
    --robot.left_arm_config.side=left \
    --robot.right_arm_config.port=can1 \
    --robot.right_arm_config.side=right \
    --robot.id=my_bimanual_follower \
    --teleop.type=bi_openarm_leader \
    --teleop.left_arm_config.port=can2 \
    --teleop.right_arm_config.port=can3 \
    --teleop.id=my_bimanual_leader
```

### 数据采集

在遥操作过程中采集数据集：

```
lerobot-record \
    --robot.type=openarm_follower \
    --robot.port=can0 \
    --robot.side=right \
    --robot.id=my_follower \
    --teleop.type=openarm_leader \
    --teleop.port=can1 \
    --teleop.id=my_leader \
    --repo-id=my_hf_username/my_openarm_dataset \
    --fps=30 \
    --num-episodes=10
```

## 配置选项

### 从动臂配置

| 参数 | 默认 | 描述 |
| --- | --- | --- |
| `port` | - | CAN 接口（例如 `can0`） |
| `side` | `无` | 机械臂侧：`"left"`（左）、`"right"`（右），或 `None`（自定义限制） |
| `use_can_fd` | `True` | 启用 CAN FD 以获得更高数据速率 |
| `can_bitrate` | `1000000` | 标称比特率（1 Mbps） |
| `can_data_bitrate` | `5000000` | CAN FD 数据比特率（5 Mbps） |
| `max_relative_target` | `无` | 相对目标位置的安全限制 |
| `position_kp` | 各关节 | 位置控制比例增益 |
| `position_kd` | 各关节 | 位置控制微分增益 |

### 主动臂配置

| 参数 | 默认 | 描述 |
| --- | --- | --- |
| `port` | - | CAN 接口（例如 `can1`） |
| `manual_control` | `True` | 禁用力矩以实现手动移动 |
| `use_can_fd` | `True` | 启用 CAN FD 以获得更高数据速率 |
| `can_bitrate` | `1000000` | 标称比特率（1 Mbps） |
| `can_data_bitrate` | `5000000` | CAN FD 数据比特率（5 Mbps） |

## 电机配置

OpenArm 使用 Damiao 电机，默认配置如下：

| 关节 | 电机类型 | 发送 ID | 接收 ID |
| --- | --- | --- | --- |
| joint\_1（肩部平移） | DM8009 | 0x01 | 0x11 |
| joint\_2（肩部升降） | DM8009 | 0x02 | 0x12 |
| joint\_3（肩部旋转） | DM4340 | 0x03 | 0x13 |
| joint\_4（肘部弯曲） | DM4340 | 0x04 | 0x14 |
| joint\_5（腕部横滚） | DM4310 | 0x05 | 0x15 |
| joint\_6（腕部俯仰） | DM4310 | 0x06 | 0x16 |
| joint\_7（腕部旋转） | DM4310 | 0x07 | 0x17 |
| 夹爪 | DM4310 | 0x08 | 0x18 |

## 疑难解答

### 电机无响应

1. 检查电源连接
2. 验证 CAN 接线（CAN-H, CAN-L, GND）
3. 运行诊断：`lerobot-setup-can --mode=test --interfaces=can0`
4. 更多详情请参考[《Damiao 故障排除指南》](damiao.md#troubleshooting)

### 未找到 CAN 接口

确保已配置 CAN 接口

```
ip link show can0
```

## 资源

* [OpenArm 网站](https://openarm.dev)
* [OpenArm 文档](https://docs.openarm.dev)
* [OpenArm GitHub](https://github.com/enactic/openarm)
* [安全指南](https://docs.openarm.dev/getting-started/safety-guide)
* [达妙电机与 CAN 总线](damiao.md)

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/openarm.mdx)
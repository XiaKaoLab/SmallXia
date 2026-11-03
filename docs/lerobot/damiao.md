# 来源

https://hugging-face.cn/docs/lerobot/damiao

# 大妙电机与 CAN 总线

本指南涵盖了通过 CAN 总线通信在 LeRobot 中设置和使用大妙电机的步骤。

目前仅支持 Linux，因为 OpenArms CAN 适配器仅提供 Linux 驱动程序。

## Linux CAN 设置

在使用大妙电机之前，您需要在 Linux 系统上设置 CAN 接口。

### 安装 CAN 工具

```
sudo apt-get install can-utils
```

### 配置 CAN 接口（手动）

针对标准 CAN FD（OpenArms 推荐）

```
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000 dbitrate 5000000 fd on
sudo ip link set can0 up
```

针对标准 CAN（非 FD）

```
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

### 配置 CAN 接口（使用 LeRobot）

LeRobot 提供了一个实用脚本用于设置和测试 CAN 接口

```
# Setup multiple interfaces (e.g., OpenArms Followers with 2 CAN buses)
lerobot-setup-can --mode=setup --interfaces=can0,can1
```

## 调试 CAN 通信

使用内置的调试工具来测试电机通信

```
# Test motors on all interfaces
lerobot-setup-can --mode=test --interfaces=can0,can1

# Run speed/latency test
lerobot-setup-can --mode=speed --interfaces=can0
```

测试模式将扫描电机（ID 0x01-0x08）并报告哪些电机有响应。示例输出如下：

```
can0: UP (CAN FD)
  Motor 0x01 (joint_1): ✓ FOUND
    → Response 0x11 [FD]: 00112233...
  Motor 0x02 (joint_2): ✓ FOUND
  Motor 0x03 (joint_3): ✗ No response
  ...
  Summary: 2/8 motors found
```

## 用法

### 基础设置

```
from lerobot.motors import Motor
from lerobot.motors.damiao import DamiaoMotorsBus

# Define your motors with send/receive CAN IDs
motors = {
    "joint_1": Motor(id=0x01, motor_type_str="dm8009", recv_id=0x11),
    "joint_2": Motor(id=0x02, motor_type_str="dm4340", recv_id=0x12),
    "joint_3": Motor(id=0x03, motor_type_str="dm4310", recv_id=0x13),
}

# Create the bus
bus = DamiaoMotorsBus(
    port="can0",  # Linux socketcan interface
    motors=motors,
)

# Connect
bus.connect()
```

### 读取电机状态

```
# Read single motor position (degrees)
position = bus.read("Present_Position", "joint_1")

# Read from multiple motors
positions = bus.sync_read("Present_Position")  # All motors
positions = bus.sync_read("Present_Position", ["joint_1", "joint_2"])

# Read all states at once (position, velocity, torque)
states = bus.sync_read_all_states()
# Returns: {'joint_1': {'position': 45.2, 'velocity': 1.3, 'torque': 0.5}, ...}
```

### 写入电机指令

```
# Enable torque
bus.enable_torque()

# Set goal position (degrees)
bus.write("Goal_Position", "joint_1", 45.0)

# Set positions for multiple motors
bus.sync_write("Goal_Position", {
    "joint_1": 45.0,
    "joint_2": -30.0,
    "joint_3": 90.0,
})

# Disable torque
bus.disable_torque()
```

## 配置选项

| 参数 | 默认 | 描述 |
| --- | --- | --- |
| `port（端口）` | - | CAN 接口 (`can0`) 或串口 (`/dev/cu.usbmodem*`) |
| `use_can_fd` | `True` | 启用 CAN FD 以获得更高的数据传输速率 |
| `bitrate（波特率）` | `1000000` | 标称波特率 (1 Mbps) |
| `data_bitrate（数据波特率）` | `5000000` | CAN FD 数据波特率 (5 Mbps) |

## 电机配置

每个电机需要配置：

* `id`：用于发送指令的 CAN ID
* `motor_type`：支持的电机类型之一（例如 `"dm8009"`, `"dm4340"`）
* `recv_id`：用于接收响应的 CAN ID

OpenArms 的默认 ID 遵循以下模式：发送 ID 为 `0x0N`，接收 ID 为 `0x1N`，其中 N 是关节编号。

## 疑难解答

### 电机无响应

1. **检查电源**
2. **验证 CAN 接线**：检查 CAN-H、CAN-L 和 GND 的连接情况
3. **检查电机 ID**：使用达妙 (Damiao) 调试工具验证/配置 ID
4. **测试 CAN 接口**：运行 `candump can0` 查看是否收到消息
5. **运行诊断**：`lerobot-setup-can --mode=test --interfaces=can0`

### 电机超时参数

如果电机的 timeout 参数被配置为 0，它们将不会响应指令。请使用达妙 (Damiao) 调试工具将其设置为非零值。

### 验证 CAN FD 状态

```
ip -d link show can0 | grep fd
```

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/damiao.mdx)
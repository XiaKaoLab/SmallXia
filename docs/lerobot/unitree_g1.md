# 来源

https://hugging-face.cn/docs/lerobot/unitree_g1

# Unitree G1

![Unitree G1 locomanipulation demo](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/unitree_thumbnail.jpg)

LeRobot 现在已支持 Unitree G1 人形机器人！你可以进行远程操作、训练移动操作策略、在模拟器中进行测试等。支持 29 和 23 自由度（DoF）两种变体。

---

## 第一部分：入门指南

### 安装 Unitree SDK

请按照 [unitree\_sdk2\_python 安装指南](https://github.com/unitreerobotics/unitree_sdk2_python#installation)进行操作。测试环境为 `unitree_sdk2py==1.0.1` 和 `cyclonedds==0.10.2`

```
conda create -y -n lerobot python=3.12
conda activate lerobot
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd unitree_sdk2_python
pip install -e .
cd ..
```

### 安装 LeRobot

```
conda install ffmpeg -c conda-forge
conda install -c conda-forge "pinocchio>=3.0.0,<4.0.0"
git clone https://github.com/huggingface/lerobot.git
cd lerobot
pip install -e '.[unitree_g1]'
```

> 目前，pinocchio 必须通过 conda-forge（而非 pip）安装，以便包含手臂 IK 所需的 CasADi 绑定。

### 测试安装（仿真）

仿真环境有其自身的依赖项。请查看仿真环境依赖：[Unitree G1 Mujoco EnvHub](https://hugging-face.cn/lerobot/unitree-g1-mujoco/tree/main)。

```
pip install mujoco loguru msgpack msgpack-numpy
```

```
lerobot-teleoperate \
  --robot.type=unitree_g1 \
  --robot.is_simulation=true \
  --teleop.type=unitree_g1 \
  --teleop.id=wbc_unitree \
  --robot.cameras='{"global_view": {"type": "zmq", "server_address": "localhost", "port": 5555, "camera_name": "head_camera", "width": 640, "height": 480, "fps": 30, "warmup_s": 5}}' \
  --display_data=true \
  --robot.controller=GrootLocomotionController
```

这将为 G1 启动一个 [MuJoCo 仿真实例](https://hugging-face.cn/lerobot/unitree-g1-mujoco/tree/main)。你可以在启动前将游戏手柄连接到你的电脑，以便在仿真中控制机器人的移动。我们通过 `--robot.controller` 支持 [HolosomaLocomotionController](https://github.com/amazon-far/holosoma) 和 [GrootLocomotionController](https://github.com/NVlabs/GR00T-WholeBodyControl)。

* 按 `9` 释放机器人
* 按 `7` / `8` 增加 / 降低腰部高度

### 连接到实体机器人

G1 的以太网 IP 固定为 `192.168.123.164`。你的机器必须在同一网段拥有一个静态 IP：`192.168.123.x`，其中 `x ≠ 164`。

```
# Replace 'enp131s0' with your ethernet interface name (check with `ip a`)
sudo ip addr flush dev enp131s0
sudo ip addr add 192.168.123.200/24 dev enp131s0
sudo ip link set enp131s0 up
```

### 通过 SSH 登录机器人

```
ssh unitree@192.168.123.164
# Password: 123
```

### 通过以太网共享网络

G1 需要互联网访问来克隆仓库和安装软件包。请通过以太网共享你笔记本电脑的连接

**在你的笔记本电脑上**

```
sudo sysctl -w net.ipv4.ip_forward=1

# Replace wlp132s0f0 with your WiFi interface name
sudo iptables -t nat -A POSTROUTING -o wlp132s0f0 -s 192.168.123.0/24 -j MASQUERADE
sudo iptables -A FORWARD -i wlp132s0f0 -o enp131s0 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i enp131s0 -o wlp132s0f0 -j ACCEPT
```

**在 G1 上**

```
sudo ip route del default 2>/dev/null || true
sudo ip route add default via 192.168.123.200 dev eth0
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

# Verify
ping -c 3 8.8.8.8
```

### 在 G1 上安装 Unitree SDK

请按照 [unitree\_sdk2\_python 安装指南](https://github.com/unitreerobotics/unitree_sdk2_python#installation)进行操作

```
conda create -y -n lerobot python=3.12
conda activate lerobot
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd unitree_sdk2_python
python -m pip install -e .
cd ..
```

### 在 G1 上安装 LeRobot

```
git clone https://github.com/huggingface/lerobot.git
cd lerobot
conda install -c conda-forge "pinocchio>=3.0.0,<4.0.0"
python -m pip install -e '.[unitree_g1]'
```

> 目前，pinocchio 必须通过 conda-forge（而非 pip）安装，以便包含手臂 IK 所需的 CasADi 绑定。

### （可选）在机器人上启用 WiFi

为了实现无线 SSH 访问，你可以在 G1 上启用 WiFi（默认情况下它是禁用的）

```
sudo rfkill unblock all
sudo ip link set wlan0 up
sudo nmcli radio wifi on
sudo nmcli device set wlan0 managed yes
sudo systemctl restart NetworkManager
```

**连接到 WiFi 网络**

```
nmcli device wifi list

sudo nmcli connection add type wifi ifname wlan0 con-name "YourNetwork" ssid "YourNetwork"
sudo nmcli connection modify "YourNetwork" wifi-sec.key-mgmt wpa-psk
sudo nmcli connection modify "YourNetwork" wifi-sec.psk "YourPassword"
sudo nmcli connection modify "YourNetwork" connection.autoconnect yes
sudo nmcli connection up "YourNetwork"

ip a show wlan0
```

然后你就可以通过 WiFi 而非以太网进行 SSH 登录

```
ssh unitree@<ROBOT_WIFI_IP>
# Password: 123
```

---

## 第二部分：远程操作与移动

### 运行机器人服务器

在机器人上（从 `~/lerobot` 目录）

```
cd ~/lerobot
python src/lerobot/robots/unitree_g1/run_g1_server.py --camera
```

### 运行移动策略

你可以通过以太网、WiFi（实验性）在笔记本电脑上运行远程操作客户端，或者直接在机器人上运行。请注意网络可能带来的延迟。

**从你的笔记本电脑**

```
lerobot-teleoperate \
  --robot.type=unitree_g1 \
  --robot.is_simulation=false \
  --robot.robot_ip=<ROBOT_IP> \
  --teleop.type=unitree_g1 \
  --teleop.id=wbc_unitree \
  --robot.cameras='{"global_view": {"type": "zmq", "server_address": "<ROBOT_IP>", "port": 5555, "camera_name": "head_camera", "width": 640, "height": 480, "fps": 30}}' \
  --display_data=true \
  --robot.controller=HolosomaLocomotionController
```

我们通过 `--robot.controller` 同时支持 [GrootLocomotionController](https://github.com/NVlabs/GR00T-WholeBodyControl) 和 [HolosomaLocomotionController](https://github.com/amazon-far/holosoma)。

---

## 第三部分：使用 Homunculus 外骨骼进行移动操作

我们通过 Homunculus 外骨骼提供移动操作方案——这是一个用于全身控制的开源 7 自由度外骨骼。可以在[此处](https://github.com/nepyope/hmc_exo)查看。

### 校准

```
lerobot-calibrate \
  --teleop.type=unitree_g1 \
  --teleop.left_arm_config.port=/dev/ttyACM1 \
  --teleop.right_arm_config.port=/dev/ttyACM0 \
  --teleop.id=exo
```

在校准期间，移动每个关节至其整个活动范围。适配后，将关节移动到中性位置，按 `n` 继续。

### 记录数据集

```
lerobot-record \
  --robot.type=unitree_g1 \
  --robot.is_simulation=true \
  --robot.cameras='{"global_view": {"type": "zmq", "server_address": "localhost", "port": 5555, "camera_name": "head_camera", "width": 640, "height": 480, "fps": 30}}' \
  --teleop.type=unitree_g1 \
  --teleop.left_arm_config.port=/dev/ttyACM1 \
  --teleop.right_arm_config.port=/dev/ttyACM0 \
  --teleop.id=exo \
  --dataset.repo_id=your-username/dataset-name \
  --dataset.single_task="Test" \
  --dataset.num_episodes=2 \
  --dataset.episode_time_s=5 \
  --dataset.reset_time_s=5 \
  --dataset.push_to_hub=true \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2
```

> **注意：** 如果你仅使用操纵杆，请省略 `--teleop.left_arm_config.port` 和 `--teleop.right_arm_config.port`。

示例数据集：[nepyope/unitree\_box\_move\_blue\_full](https://hugging-face.cn/datasets/nepyope/unitree_box_move_blue_full)

---

## 第四部分：训练与推理

### 训练

```
python src/lerobot/scripts/lerobot_train.py \
  --dataset.repo_id=your-username/dataset-name  \
  --policy.type=pi05 \
  --output_dir=./outputs/pi05_training \
  --job_name=pi05_training \
  --policy.repo_id=your-username/your-repo-id \
  --policy.pretrained_path=lerobot/pi05_base \
  --policy.compile_model=true \
  --policy.gradient_checkpointing=true \
  --wandb.enable=true \
  --policy.dtype=bfloat16 \
  --policy.freeze_vision_encoder=false \
  --policy.train_expert_only=false \
  --steps=3000 \
  --policy.device=cuda \
  --batch_size=32
```

### 通过 RTC 进行推理

训练完成后，我们建议使用推理时 RTC 来部署策略

```
python examples/rtc/eval_with_real_robot.py \
  --policy.path=your-username/your-repo-id \
  --policy.device=cuda \
  --robot.type=unitree_g1 \
  --robot.is_simulation=false \
  --robot.controller=HolosomaLocomotionController \
  --robot.cameras='{"global_view": {"type": "zmq", "server_address": "<ROBOT_IP>", "port": 5555, "camera_name": "head_camera", "width": 640, "height": 480, "fps": 30}}' \
  --task="task_description" \
  --duration=1000 \
  --fps=30 \
  --rtc.enabled=true
```

---

## 附加资源

* [Unitree SDK 文档](https://github.com/unitreerobotics/unitree_sdk2_python)
* [GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl)
* [Holosoma](https://github.com/amazon-far/holosoma)
* [LeRobot 文档](https://github.com/huggingface/lerobot)
* [Unitree IL LeRobot](https://github.com/unitreerobotics/unitree_IL_lerobot)

---

*最后更新：2026 年 3 月*

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/unitree_g1.mdx)
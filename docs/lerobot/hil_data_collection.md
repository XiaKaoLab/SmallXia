# 来源

https://hugging-face.cn/docs/lerobot/hil_data_collection

# 人在回路数据收集

人在回路 (HIL) 数据收集允许您在真实机器人上部署经过训练的策略，同时由人类操作员进行监控并在必要时介入。干预数据（恢复动作和修正）会与自主运行片段一同被记录，从而生成更丰富的训练数据集，教会策略如何处理故障。

---

## 为什么要采用人在回路？

标准的行为克隆仅基于成功的演示来训练策略。在部署期间，微小的误差可能会累积，导致机器人进入训练过程中从未见过的状态（分布偏移）。HIL 数据收集通过以下方式解决该问题：

* 在真实机器人上运行经过训练的策略
* 当机器人即将失败时，由人类进行干预
* 将人类的恢复和修正操作记录为训练数据
* 在合并后的数据集上对策略进行微调

这产生的策略不仅知道如何完成任务，还知道在出错时如何进行自我恢复。

---

## 工作原理

在 HIL 会话期间，人类操作员在每次实验中遵循以下循环：

1. **观察**：策略自主运行
2. **暂停**：在即将失败时按下暂停，机器人保持当前位置
3. **接管控制**：遥操作机器人回到良好状态（恢复），然后修正行为
4. **交还控制权**：策略恢复自主执行
5. 在实验期间根据需要重复上述第 2–4 步
6. **结束实验**：任务完成后保存数据，并继续进行下一次 rollout

自主片段和人类控制片段都会被记录下来。策略与人类可以在单次实验中多次交替控制，且每次移交后实验都会从当前状态继续（无需因为干预而重置）。这在一段连续的轨迹中捕捉了自主执行、恢复和修正过程。收集完成后，合并后的数据集（原始演示 + HIL 数据）将用于微调策略。

此过程可以迭代重复：部署、收集、微调、循环。每一轮都针对当前策略的失败模式进行优化。

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Policy v0 (trained on demos)                                           │
│       ↓                                                                 │
│  HIL Collection (target current failure modes) → Fine-tune → Policy v1  │
│       ↓                                                                 │
│  HIL Collection (target new failure modes) → Fine-tune → Policy v2      │
│       ↓                                                                 │
│  ... (repeat until satisfactory performance)                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 硬件要求

### 遥操作设备要求

`examples/hil` 中的 HIL 脚本需要**配备主动电机的遥操作设备**，能够：

* 通过程序启用/禁用扭矩
* 移动到目标位置（在暂停时与机器人状态保持一致）

**当前 `examples/hil` 脚本中兼容的遥操作设备：**

* `openarm_mini` - OpenArm Mini
* `so_leader` - SO100 / SO101 引导臂

> 提供的 `examples/hil` 命令默认使用 `bi_openarm_follower` + `openarm_mini`。`so_follower` + `so_leader` 配置也已注册，可以通过 CLI 标志使用。

---

## 脚本

单个脚本同时处理同步和基于 RTC 的推理。使用 `--rtc.enabled=true` 切换 RTC。

| 模式 | 标志 | 模型 |
| --- | --- | --- |
| 标准（默认） | *（无需任何标志）* | ACT, Diffusion Policy |
| 实时分块 (Real-Time Chunking, RTC) | `--rtc.enabled=true` | Pi0, Pi0.5, SmolVLA |

---

## 逐步指南

### 第 1 步：预训练基础策略

首先，在您的演示数据集上训练一个策略。

```
python src/lerobot/scripts/lerobot_train.py \
    --dataset.repo_id=your-username/demo-dataset \
    --policy.type=pi0 \
    --output_dir=outputs/pretrain \
    --batch_size=32 \
    --steps=50000
```

### 第 2 步：收集 HIL 数据

**标准推理 (ACT, Diffusion Policy)**

```
python examples/hil/hil_data_collection.py \
    --robot.type=bi_openarm_follower \
    --robot.left_arm_config.port=can1 \
    --robot.left_arm_config.side=left \
    --robot.right_arm_config.port=can0 \
    --robot.right_arm_config.side=right \
    --robot.cameras='{left_wrist: {type: opencv, index_or_path: "/dev/video0", width: 1280, height: 720, fps: 30}, right_wrist: {type: opencv, index_or_path: "/dev/video4", width: 1280, height: 720, fps: 30}, base: {type: opencv, index_or_path: "/dev/video2", width: 640, height: 480, fps: 30}}' \
    --teleop.type=openarm_mini \
    --teleop.port_left=/dev/ttyACM0 \
    --teleop.port_right=/dev/ttyACM1 \
    --policy.path=outputs/pretrain/checkpoints/last/pretrained_model \
    --dataset.repo_id=your-username/hil-dataset \
    --dataset.single_task="Fold the T-shirt properly" \
    --dataset.fps=30 \
    --dataset.episode_time_s=1000 \
    --dataset.num_episodes=50 \
    --interpolation_multiplier=2
```

**针对大模型（Pi0, Pi0.5, SmolVLA）使用 RTC**

对于具有高推理延迟的模型，请启用 RTC 以实现平滑执行。

```
python examples/hil/hil_data_collection.py \
    --rtc.enabled=true \
    --rtc.execution_horizon=20 \
    --rtc.max_guidance_weight=5.0 \
    --rtc.prefix_attention_schedule=LINEAR \
    --robot.type=bi_openarm_follower \
    --robot.left_arm_config.port=can1 \
    --robot.left_arm_config.side=left \
    --robot.right_arm_config.port=can0 \
    --robot.right_arm_config.side=right \
    --robot.cameras='{left_wrist: {type: opencv, index_or_path: "/dev/video0", width: 1280, height: 720, fps: 30}, right_wrist: {type: opencv, index_or_path: "/dev/video4", width: 1280, height: 720, fps: 30}, base: {type: opencv, index_or_path: "/dev/video2", width: 640, height: 480, fps: 30}}' \
    --teleop.type=openarm_mini \
    --teleop.port_left=/dev/ttyACM0 \
    --teleop.port_right=/dev/ttyACM1 \
    --policy.path=outputs/pretrain/checkpoints/last/pretrained_model \
    --dataset.repo_id=your-username/hil-rtc-dataset \
    --dataset.single_task="Fold the T-shirt properly" \
    --dataset.fps=30 \
    --dataset.episode_time_s=1000 \
    --dataset.num_episodes=50 \
    --interpolation_multiplier=3
```

**控制（概念）**

交互模型如下：

* **暂停输入**：暂停自主策略执行
* **接管输入**：将控制权转移给人类操作员并记录干预数据
* **交还策略输入**：将控制权交还给策略并继续当前的同一实验
* **实验控制输入**：根据需要保存/重新录制/停止/重置

确切的按键/踏板绑定可能因脚本和硬件集成而异。请以每个脚本输出的控制说明作为您设置中具体映射的权威参考。

**HIL 协议**

1. 观察策略自主运行（遥操作设备处于空闲/自由状态）
2. 当看到即将发生故障时，触发**暂停输入**
   * 策略停止
   * 遥操作设备移动以匹配机器人位置（扭矩已启用）
   * 暂停期间不记录帧
3. 触发**接管输入**以获取控制权
   * 遥操作设备扭矩已禁用，可自由移动
   * **恢复**：遥操作机器人回到良好状态
   * **修正**：修正行为
   * 所有动作都会被记录
4. 触发**交还策略输入**
   * 策略从当前状态恢复自主执行
   * 您可以随时再次干预（重复步骤 2–4）
5. 任务完成后（或达到实验时间限制时）结束并保存实验
6. **重置**：遥操作设备移动到机器人位置，您可以将机器人移至起始位置
7. 开始下一次实验

**脚踏板设置 (Linux)**

如果使用 USB 脚踏板 (PCsensor FootSwitch)，请确保拥有访问权限

```
sudo setfacl -m u:$USER:rw /dev/input/by-id/usb-PCsensor_FootSwitch-event-kbd
```

### 第 3 步：微调策略

在**合并后**的数据集（`demo-dataset` + `hil-dataset` 合并）上进行微调。

```
python src/lerobot/scripts/lerobot_train.py \
    --dataset.repo_id=your-username/hil-dataset \
    --policy.type=pi0 \
    --policy.pretrained_path=outputs/pretrain/checkpoints/last/pretrained_model \
    --output_dir=outputs/hil_finetune \
    --steps=20000
```

然后部署微调后的策略，并从第 2 步开始重复，以解决其剩余的故障模式。

---

## 有效 HIL 收集的提示

### 何时进行干预

当发现以下情况时进行干预：

* 机器人即将犯下不可逆转的错误
* 机器人犹豫不决或表现出不确定的行为
* 机器人偏离了预期的轨迹

### 恢复：遥操作回到良好状态

在恢复期间，遥操作机器人回到以下状态：

* 处于熟悉且符合分布的配置中
* 当前的子任务仍可完成
* 恢复轨迹本身也是具有参考价值的训练数据

### 修正质量

在修正期间：

* 提供**自信、干净**的轨迹
* 完整地完成当前子任务
* 不要过度矫正或增加不必要的动作

---

## 相关工作

这种 HIL 数据收集方法建立在交互式模仿学习的思想之上。

* **DAgger** (Ross et al., 2011) 引入了核心思想：不仅要基于专家演示进行训练，还要让专家对*学习者*访问的状态提供修正。这通过迭代收集在策略（on-policy）数据，打破了标准行为克隆的误差累积循环。
* **HG-DAgger** (Kelly et al., 2019) 使其在机器人领域具备了实用性：人类专家监控机器人并仅在需要时介入，而不是标记每个状态。自主控制与人工控制之间的门控机制，正是本文脚本中使用的“暂停 → 接管 → 交还策略”循环。
* **RaC** (Hu et al., 2025) 将该循环扩展到长跨度任务，将干预明确分解为**恢复**（遥操作回到良好状态）和**修正**（从该处演示正确行为）。这种分解是 `examples/hil` 中 HIL 脚本遵循的协议。
* **π0.6/RECAP** (Physical Intelligence, 2025) 将相同的迭代收集与微调循环应用于大规模 VLA 模型，证明了即使是大型预训练策略也受益于对其失败模式进行的有针对性的人工修正。π0.6 是使用 RECAP 训练的。

```
@article{ross2011dagger,
  title={A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning},
  author={Ross, Stéphane and Gordon, Geoffrey and Bagnell, Drew},
  journal={Proceedings of the Fourteenth International Conference on Artificial Intelligence and Statistics},
  year={2011}
}

@article{kelly2019hgdagger,
  title={HG-DAgger: Interactive Imitation Learning with Human Experts},
  author={Kelly, Michael and Sidrane, Chelsea and Driggs-Campbell, Katherine and Kochenderfer, Mykel J},
  journal={arXiv preprint arXiv:1810.02890},
  year={2019}
}

@article{hu2025rac,
  title={RaC: Robot Learning for Long-Horizon Tasks by Scaling Recovery and Correction},
  author={Hu, Zheyuan and Wu, Robyn and Enock, Naveen and Li, Jasmine and Kadakia, Riya and Erickson, Zackory and Kumar, Aviral},
  journal={arXiv preprint arXiv:2509.07953},
  year={2025}
}

@article{pi2025recap,
  title={π0.6: a VLA That Learns From Experience},
  author={Physical Intelligence},
  year={2025}
}
```

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/hil_data_collection.mdx)
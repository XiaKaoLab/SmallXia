# 来源

https://hugging-face.cn/docs/lerobot/rtc

# 实时分块 (Real-Time Chunking, RTC)

实时分块 (RTC) 是一种推理时方法，它允许基于流匹配 (flow-matching) 的大型机器人策略（如 [Pi0](pi0.md), [Pi0.5](pi05.md) 和 [SmolVLA](smolvla.md)）在具有高推理延迟的情况下，依然能产生平滑、连续且具有响应性的运动。

这些策略生成的是未来动作的分块（例如一次生成 50 个步骤），而不是单个动作。由于模型规模较大，产生每个分块所需的时间长于机器人执行该分块所需的时间。如果直接执行分块，会导致在下一个分块延迟到达或与之前执行的动作不一致时，出现停顿、过渡僵硬或策略突然改变等问题。

RTC 通过在机器人继续执行当前分块的同时，异步生成下一个分块，并引导新分块使其与已执行的前一分块部分平滑对齐，从而解决了这一问题。

## RTC 工作原理（简化版）

RTC 让机器人在运动的同时进行“预判”。当机器人正在执行一组动作分块时，RTC 会提前开始创建下一个分块。但由于新分块准备好时，机器人已经移动了一段距离，因此 RTC 必须确保新分块与机器人当前的动作依然能平滑衔接。

为了实现这一点，RTC 将新分块的开始部分视为一个图像补全 (inpainting) 或“填空”问题：它会轻轻调整新分块的第一部分，使其与机器人正在进行的运动自然融合。结果就是没有停顿，没有突然的跳变。

从技术角度来看，RTC 在流匹配去噪过程中增加了一个引导项 (guidance term)，强制新分块的重叠时间步与前一分块的已执行部分保持接近，通常使用一个软过渡掩码 (soft transition mask) 来实现。

## 快速开始

### 安装

RTC 已内置在 LeRobot 中。只需安装所需的策略依赖项即可

```
# For Pi0 or Pi0.5
pip install -e ".[pi]"

# For SmolVLA
pip install -e ".[smolvla]"
```

### 在 Pi0 中使用 RTC

您可以在 [eval\_with\_real\_robot.py](https://hugging-face.cn/docs/lerobot/examples/rtc/eval_with_real_robot.py) 中找到完整的参考实现。下面的代码片段提供了一个简化后的伪示例，展示了 RTC 在您的流水线中如何与 Pi0 协同工作

```
from lerobot.policies.pi0 import PI0Policy, PI0Config
from lerobot.configs.types import RTCAttentionSchedule
from lerobot.policies.rtc.configuration_rtc import RTCConfig
from lerobot.policies.rtc.action_queue import ActionQueue

# Load Pi0 with RTC enabled
policy_cfg = PI0Config()

# Enable RTC
policy_cfg.rtc_config = RTCConfig(
    enabled=True,
    execution_horizon=10,  # How many steps to blend with previous chunk
    max_guidance_weight=10.0,  # How strongly to enforce consistency
    prefix_attention_schedule=RTCAttentionSchedule.EXP,  # Exponential blend
)

# Load the policy
policy = PI0Policy.from_pretrained("lerobot/pi0_base", policy_cfg=policy_cfg, device="cuda")

# Now use predict_action_chunk with RTC parameters
inference_delay = 4  # How many steps of inference latency, this values should be calculated based on the inference latency of the policy

# Initialize the action queue
action_queue = ActionQueue(policy_cfg.rtc_config)

# Start in a separate thread with the following function
def get_actions():
  while True:
    if should_get_actions:

      prev_actions = action_queue.get_left_over()
      obs = get_robot_observations(robot)

      # Generate actions WITH RTC
      actions = policy.predict_action_chunk(
          obs,
          inference_delay=inference_delay,
          prev_chunk_left_over=prev_actions,
      )

      action_queue.merge(
          actions, actions, inference_delay
      )

for step in range(num_steps):
    action = action_queue.get()

    # Execute the first N actions
    execute_actions(action)
```

## 关键参数

`RTCConfig` 具有以下可调参数

**`execution_horizon`**：与前一分块保持一致的时间步数。值越高意味着过渡越平滑，但响应性可能会降低。

典型值：8-12 步

```
RTCConfig(execution_horizon=10)
```

**`max_guidance_weight`**：强制与前一分块保持一致的强度。这是一个超参数，可用于在过渡平滑度和策略响应性之间取得平衡。对于 10 步流匹配（SmolVLA, Pi0, Pi0.5），10.0 是一个最优值。

**`prefix_attention_schedule`**：如何在重叠区域分配一致性权重。

* `LINEAR`：从 inference\_delay 到 execution\_horizon 的线性衰减
* `EXP`：指数衰减（推荐入门使用）
* `ONES`：在整个 execution\_horizon 范围内使用全权重
* `ZEROS`：二进制（直到 inference\_delay 使用全权重，之后为零）

**`inference_delay`**：系统的推理延迟时间步数。由于它在运行时可能会有所变化，因此该值传递给 `predict_action_chunk()` 而不是配置项。

## 离线测试 RTC

在真实机器人上运行之前，可以使用数据集样本测试 RTC 以可视化其工作方式

```
python examples/rtc/eval_dataset.py \
    --policy.path=lerobot/pi0_libero_finetuned \
    --dataset.repo_id=HuggingFaceVLA/libero \
    --rtc.execution_horizon=10 \
    --rtc.max_guidance_weight=10.0 \
    --device=cuda
```

该脚本会生成去噪过程的可视化图表，将标准生成（左）与 RTC（右）进行对比。在 RTC 图表中，您可以看到前几个步骤（蓝色/紫色线）是如何被引导以匹配红色地面真值轨迹（前一分块的末尾），从而确保分块之间的平滑过渡。

![Denoising steps with and without RTC](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/lerobot/flow_matching.png)

## 使用真实机器人测试 RTC

```
python examples/rtc/eval_with_real_robot.py \
    --policy.path=${HF_USERNAME}/policy_repo_id \
    --robot.type=so100_follower \
    --robot.port=/dev/tty.usbmodem58FA0834591 \
    --robot.cameras="{ gripper: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
    --task="Move green small object into the purple platform" \
    --duration=120 \
    --device=cuda
```

## 它与 LeRobot 中的异步推理有何不同

RTC 和 [异步推理 (async inference)](async.md) 都能提高机器人的实时控制能力，但它们解决的是不同的问题。

| 方面 | 异步推理 | RTC |
| --- | --- | --- |
| **问题** | 等待推理时的空闲帧 | 动作分块之间的不连续性 |
| **解决方案** | 将预测与执行解耦 | 引导新分块平滑地接续前一个分块 |
| **好处** | 无等待，动作连续 | 平滑过渡，运动自然 |
| **最佳适用场景** | 异步推理最适用于具有高推理延迟的大模型 | 基于流匹配的策略 |

**将两者结合使用**，以获得最佳的平滑度和响应性！

## 进阶：调试跟踪

RTC 包含内置的调试跟踪功能，帮助您了解推理过程中发生了什么

```
# Enable debug tracking
policy_cfg.rtc_config.debug = True
policy_cfg.rtc_config.debug_maxlen = 100

# After inference, access debug data
debug_data = policy.rtc_processor.get_debug_data()

# Visualize denoising steps, corrections, etc.
from lerobot.policies.rtc.debug_visualizer import RTCDebugVisualizer
visualizer = RTCDebugVisualizer()
# ... create plots
```

请参阅 `examples/rtc/eval_dataset.py` 以获取完整的可视化示例。

## 参考文献

* [Smooth-As-Butter Robot Policies](https://alexander-soare.github.io/robotics/2025/08/05/smooth-as-butter-robot-policies.html) - 包含真实机器人结果的极佳技术解析
* [Physical Intelligence - Real-Time Chunking](https://www.physicalintelligence.company/research/real_time_chunking) - 原始论文与研究
* [Kinetix RTC 实现](https://github.com/Physical-Intelligence/real-time-chunking-kinetix) - 来自 Physical Intelligence 的参考实现

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/rtc.mdx)
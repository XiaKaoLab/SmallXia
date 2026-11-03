# 来源

https://hugging-face.cn/docs/lerobot/async

# 异步推理

随着 [SmolVLA](https://hugging-face.cn/papers/2506.01844) 的发布，我们引入了一种在现实世界机器人上运行推理的新方法，即**将动作预测与动作执行解耦**。在本教程中，我们将展示如何使用经过微调的 SmolVLA 版本以及 LeRobot 支持的所有策略来使用异步推理（*async inference*）。**尝试使用 LeRobot 支持的所有策略来体验异步推理吧！**

**你将学到什么**

1. 为什么异步推理很重要，以及它与更传统的同步推理相比如何。
2. 如何启动 `PolicyServer`（策略服务器）并从同一台机器甚至通过网络连接 `RobotClient`（机器人客户端）。
3. 如何为你的机器人和策略调整关键参数（`actions_per_chunk`, `chunk_size_threshold`）。

如果你遇到了困难，欢迎加入我们的 [Discord 社区](https://discord.gg/s3KuuzsPFb)！

简而言之：通过*异步推理*，当策略服务器忙于计算下一批动作时，你的机器人可以保持动作不间断——消除了“等待推理”造成的延迟，并解锁了更流畅、响应更灵敏的行为。这与同步推理（sync）有本质区别，在同步推理中，机器人必须在策略计算下一批动作时保持空闲。

---

## 异步推理入门

你可以在我们的 [博客文章](https://hugging-face.cn/blog/async-robot-inference) 中阅读有关异步推理的更多信息。本指南旨在帮助你在环境中快速设置并运行异步推理。

首先，使用 `async` 标签安装 `lerobot`，以安装运行异步推理所需的额外依赖项。

```
pip install -e ".[async]"
```

然后，启动策略服务器（在一个终端或单独的机器中），并指定客户端连接的主机地址和端口。你可以通过以下命令启动策略服务器：

```
python -m lerobot.async_inference.policy_server \
     --host=127.0.0.1 \
     --port=8080
```

这将启动一个监听在 `127.0.0.1:8080`（`localhost`，端口 8080）的策略服务器。在此阶段，策略服务器是空的，因为与运行哪种策略以及使用哪些参数相关的所有信息都是在与客户端的第一次握手期间指定的。通过以下命令启动客户端：

```
python -m lerobot.async_inference.robot_client \
    --server_address=127.0.0.1:8080 \ # SERVER: the host address and port of the policy server
    --robot.type=so100_follower \ # ROBOT: your robot type
    --robot.port=/dev/tty.usbmodem585A0076841 \ # ROBOT: your robot port
    --robot.id=follower_so100 \ # ROBOT: your robot id, to load calibration file
    --robot.cameras="{ laptop: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}, phone: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}}" \ # POLICY: the cameras used to acquire frames, with keys matching the keys expected by the policy
    --task="dummy" \ # POLICY: The task to run the policy on (`Fold my t-shirt`). Not necessarily defined for all policies, such as `act`
    --policy_type=your_policy_type \ # POLICY: the type of policy to run (smolvla, act, etc)
    --pretrained_name_or_path=user/model \ # POLICY: the model name/path on server to the checkpoint to run (e.g., lerobot/smolvla_base)
    --policy_device=mps \ # POLICY: the device to run the policy on, on the server (cuda, mps, xpu, cpu)
    --actions_per_chunk=50 \ # POLICY: the number of actions to output at once
    --chunk_size_threshold=0.5 \ # CLIENT: the threshold for the chunk size before sending a new observation to the server
    --aggregate_fn_name=weighted_average \ # CLIENT: the function to aggregate actions on overlapping portions
    --debug_visualize_queue_size=True # CLIENT: whether to visualize the queue size at runtime
```

总之，你需要为以下内容指定说明：

* `SERVER`：策略服务器的地址和端口
* `ROBOT`：要连接的机器人类型、连接端口以及机器人的本地 `id`
* `POLICY`：要运行的策略类型，以及服务器上要运行的检查点的模型名称/路径。你还需要指定服务器应使用哪个设备，以及一次输出多少个动作（上限为策略的最大动作数）。
* `CLIENT`：向服务器发送新观测数据之前的块大小阈值，以及聚合重叠部分动作的函数。此外，你还可以选择在运行时可视化队列大小，以帮助你调整 `CLIENT` 参数。

重要提示：

* `actions_per_chunk`（每块动作数）和 `chunk_size_threshold`（块大小阈值）是针对你的设置进行调整的关键参数。
* `aggregate_fn_name` 是用于聚合重叠部分动作的函数。你可以将新函数添加到函数注册表中，或者在 `robot_client.py` 中添加你自己的函数（详见 [此处](NOTE:addlinktoLOC)）。
* `debug_visualize_queue_size` 是调整 `CLIENT` 参数的有用工具。

## 搞定！现在你应该能看到机器人开始移动了 😉

## 异步推理 vs. 同步推理

同步推理依赖于交替进行动作块预测和动作执行。这固有地导致了*空闲帧*的存在，即机器人因为等待策略输出新动作块而不得不保持空闲的帧。反过来，推理过程也会受到明显的实时延迟影响，导致机器人仅仅因为缺乏可用动作而停止行动。随着机器人模型规模的不断增大，这一问题可能会变得更加严重。

![](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/async-inference/sync.png)

*同步推理*使得机器人在策略计算下一块动作时处于空闲状态。

为了克服这一点，我们设计了异步推理，这是一种将动作规划与执行解耦的范式，从而实现：(1) 更高的适应性，以及最重要的 (2) 无空闲帧。关键在于，通过异步推理，下一批动作块会在当前动作块耗尽*之前*被计算出来，从而消除了空闲状态。通过对重叠部分的动作块进行聚合，可以获得最新的规划和更紧密的控制回路，从而确保了更高的适应性。

![](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/async-inference/async.png)

*异步推理*消除了空闲状态，因为下一块动作会在当前块耗尽之前完成计算。

---

## 启动策略服务器

策略服务器是 `PreTrainedPolicy` 的包装器，用于连接机器人客户端传来的观测数据。策略服务器初始化为空容器，在机器人客户端与策略服务器之间的初始握手期间，根据请求填充指定的策略。因此，启动策略服务器就像指定主机地址和端口一样简单。如果你在与机器人客户端相同的机器上运行策略服务器，可以使用 `localhost` 作为主机地址。

命令

API 示例

```
python -m lerobot.async_inference.policy_server \
     --host=127.0.0.1 \
     --port=8080
```

这将在 `localhost:8080` 上监听来自关联的 `RobotClient` 的传入连接，客户端将在第一次客户端-服务器握手期间告知服务器运行哪种策略。

---

## 启动机器人客户端

`RobotClient` 是 `Robot` 实例的包装器，它将机器人连接到（可能是远程的）`PolicyServer`。`RobotClient` 将观测数据流式传输到 `PolicyServer`，并接收在服务器上运行推理获得的动作块（我们假设服务器比机器人控制器拥有更好的计算资源）。

命令

API 示例

```
python -m lerobot.async_inference.robot_client \
    --server_address=127.0.0.1:8080 \ # SERVER: the host address and port of the policy server
    --robot.type=so100_follower \ # ROBOT: your robot type
    --robot.port=/dev/tty.usbmodem585A0076841 \ # ROBOT: your robot port
    --robot.id=follower_so100 \ # ROBOT: your robot id, to load calibration file
    --robot.cameras="{ laptop: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}, phone: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}}" \ # POLICY: the cameras used to acquire frames, with keys matching the keys expected by the policy
    --task="dummy" \ # POLICY: The task to run the policy on (`Fold my t-shirt`). Not necessarily defined for all policies, such as `act`
    --policy_type=your_policy_type \ # POLICY: the type of policy to run (smolvla, act, etc)
    --pretrained_name_or_path=user/model \ # POLICY: the model name/path on server to the checkpoint to run (e.g., lerobot/smolvla_base)
    --policy_device=mps \ # POLICY: the device to run the policy on, on the server
    --actions_per_chunk=50 \ # POLICY: the number of actions to output at once
    --chunk_size_threshold=0.5 \ # CLIENT: the threshold for the chunk size before sending a new observation to the server
    --aggregate_fn_name=weighted_average \ # CLIENT: the function to aggregate actions on overlapping portions
    --debug_visualize_queue_size=True # CLIENT: whether to visualize the queue size at runtime
```

以下两个参数在每个设置中都至关重要：

| 超参数 | 默认 | 它的作用 |
| --- | --- | --- |
| `actions_per_chunk（每块动作数）` | 50 | 策略一次输出的动作数量。典型值：10-50。 |
| `chunk_size_threshold（块大小阈值）` | 0.7 | 当队列容量 ≤ 50% 时，客户端会发送新的观测数据。取值范围 [0, 1]。 |

> `actions\_per\_chunk` 和 `chunk\_size\_threshold` 的不同取值会导致不同的行为。

一方面，增加 `actions_per_chunk` 的值会减少“无动作可执行”的情况，因为当计算出新块时，会有更多的可用动作。然而，较大的 `actions_per_chunk` 值也可能导致动作精度下降，这是因为在较长时间跨度内预测动作会产生累积误差。

另一方面，增加 `chunk_size_threshold` 的值会导致更频繁地向 `PolicyServer` 发送推理观测数据，从而产生大量更新的动作块，并在很大程度上相互重叠。这带来了高适应性，在极限情况下，即为每个观测数据预测一个动作块，而在生成新动作块的同时仅消耗极少部分。这种选择也会由于频繁的请求而对推理流水线施加更大压力。相反，接近 0.0 的 `chunk_size_threshold` 值会退化为同步边缘情况，即仅在当前动作块耗尽时才发送新的观测数据。

我们发现在为 [SmolVLA 论文](https://hugging-face.cn/papers/2506.01844) 开发的实验中，默认的 `actions_per_chunk` 和 `chunk_size_threshold` 值运行良好，但我们建议尝试不同的值以找到最适合你设置的配置。

### 为你的设置调整异步推理

1. **谨慎选择你的计算资源。** [PI0](https://hugging-face.cn/lerobot/pi0) 在推理时占用 14GB 内存，而 [SmolVLA](https://hugging-face.cn/lerobot/smolvla_base) 仅需约 2GB。你应该根据你的用例确定最佳计算资源，并记住较小的策略需要较少的计算资源。策略与所用设备（CPU 密集型、使用 MPS，或特定 NVIDIA GPU 上的 CUDA 核心数量）的组合直接影响预期的平均推理延迟。
2. **根据推理延迟调整 `fps`。** 当服务器生成新动作块时，客户端不会闲置，而是会按照当前的动作队列执行动作。如果这两个过程以根本不同的速度运行，客户端最终可能会出现空队列。因此，如果你的队列频繁耗尽动作，应该降低 fps。
3. **调整 `chunk_size_threshold`**.
   * 接近 `0.0` 的值会导致接近顺序的行为。接近 `1.0` 的值 → 每一帧都发送观测数据（带宽占用更高，依赖于良好的世界模型）。
   * 我们发现 0.5-0.6 左右的值运行良好。如果你想微调此项，请通过设置 `--debug_visualize_queue_size` 为 `True` 来启动 `RobotClient`。这将在运行时绘制动作队列大小的变化，你可以利用它找到最适合你设置的 `chunk_size_threshold` 值。

![](https://hugging-face.cn/datasets/huggingface/documentation-images/resolve/main/async-inference/queues.png)

*当传递 `--debug\_visualize\_queue\_size` 标志时，会在运行时绘制动作队列大小，针对不同水平的 `chunk\_size\_threshold`（SmolVLA 论文中称为 `g`）。*

---

## 结论

异步推理代表了机器人实时控制的重大进步，解决了长期困扰机器人应用的推理延迟这一根本性挑战。通过本教程，你已经学习了如何实现一个完整的异步推理流水线，消除空闲帧并实现更平滑、反应更灵敏的机器人行为。

**关键要点**

* **范式转变**：异步推理将动作预测与执行解耦，允许机器人在并行计算新动作块的同时继续执行动作。
* **性能优势**：消除了同步方法中固有的“等待推理”延迟，随着策略模型变得越来越大，这一点变得越来越重要。
* **灵活架构**：服务器-客户端设计支持分布式计算，推理可以在功能强大的远程硬件上运行，同时保持机器人的实时控制。
* **可调参数**：成功取决于针对你的特定硬件、策略和任务要求正确配置 `actions_per_chunk` 和 `chunk_size_threshold`。
* **通用兼容性**：适用于所有 LeRobot 支持的策略，从轻量级 ACT 模型到像 SmolVLA 这样的视觉-语言模型。

开始使用默认参数进行实验，监控你的动作队列大小，并迭代优化你的设置，以实现针对你特定用例的最佳性能。如果你想进一步讨论，欢迎加入我们的 [Discord 社区](https://discord.gg/s3KuuzsPFb)，或在我们的 [GitHub 仓库](https://github.com/huggingface/lerobot/issues) 上提交 issue。

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/async.mdx)
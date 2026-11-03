# 来源

https://hugging-face.cn/docs/lerobot/backwardcomp

# 向后兼容性

## 策略归一化迁移 (PR #1452)

**破坏性变更**：LeRobot 策略的权重中不再包含内置的归一化层。归一化现在由外部的 `PolicyProcessorPipeline` 组件处理。

### 发生了哪些变化？

|  | PR #1452 之前 | PR #1452 之后 |
| --- | --- | --- |
| **归一化位置** | 嵌入在模型权重中 (`normalize_inputs.*`) | 外部 `PolicyProcessorPipeline` 组件 |
| **模型状态字典 (State Dict)** | 包含归一化统计数据 | **仅包含纯净权重** - 无归一化参数 |
| **用法** | `policy(batch)` 处理所有环节 | `preprocessor(batch)` → `policy(...)` → `postprocessor(...)` |

### 对现有模型的影响

* 在 PR #1452 **之前**训练的模型其归一化层嵌入在权重中
* 这些模型需要进行迁移才能与新的 `PolicyProcessorPipeline` 系统协同工作
* 迁移过程会提取归一化统计数据并创建独立的处理器流水线

### 迁移旧模型

使用迁移脚本转换带有嵌入式归一化的模型

```
python src/lerobot/processor/migrate_policy_normalization.py \
    --pretrained-path lerobot/act_aloha_sim_transfer_cube_human \
    --push-to-hub \
    --branch migrated
```

该脚本将：

1. **提取**模型权重中的归一化统计数据
2. **创建**外部预处理器 (preprocessor) 和后处理器 (postprocessor) 流水线
3. **移除**模型权重中的归一化层
4. **保存**纯净的模型 + 处理器流水线
5. **推送**至 Hub 并自动创建 PR

### 使用迁移后的模型

```
# New usage pattern (after migration)
from lerobot.policies.factory import make_policy, make_pre_post_processors

# Load model and processors separately
policy = make_policy(config, ds_meta=dataset.meta)
preprocessor, postprocessor = make_pre_post_processors(
    policy_cfg=config,
    dataset_stats=dataset.meta.stats
)

# Process data through pipeline
processed_batch = preprocessor(raw_batch)
action = policy.select_action(processed_batch)
final_action = postprocessor(action)
```

## 硬件 API 重构

PR [#777](https://github.com/huggingface/lerobot/pull/777) 改进了 LeRobot 的校准，但**不具备向后兼容性**。以下是变更概览以及您如何继续使用在该 PR 之前创建的数据集。

### 发生了哪些变化？

|  | PR #777 之前 | PR #777 之后 |
| --- | --- | --- |
| **关节范围** | 角度 `-180...180°` | **归一化范围** 关节: `–100...100` 夹持器: `0...100` |
| **零点位置 (SO100 / SO101)** | 手臂水平完全伸展 | **每个关节范围的中间位置** |
| **边界处理** | 软件保护机制用于检测 ±180° 的环绕 (wrap-arounds) | 由于零点在范围中间，无需环绕逻辑 |

---

### 对现有数据集的影响

* 在 PR #777 **之前**创建的记录轨迹如果直接加载，将无法正确回放
  + 关节角度存在偏移且归一化不正确。
* 任何直接在旧数据上微调或训练的模型都需要对其输入和输出进行转换。

### 使用之前校准系统创建的数据集

我们提供了一个迁移示例脚本，用于回放使用之前校准记录的剧集：`examples/backward_compatibility/replay.py`。下面我们将详细介绍示例脚本中为了使旧校准数据集可用而进行的修改。

```
+   key = f"{name.removeprefix('main_')}.pos"
    action[key] = action_array[i].item()
+   action["shoulder_lift.pos"] = -(action["shoulder_lift.pos"] - 90)
+   action["elbow_flex.pos"] -= 90
```

让我们详细分析一下。新代码库对位置观测使用 `.pos` 后缀，并移除了 `main_` 前缀

```
key = f"{name.removeprefix('main_')}.pos"
```

对于 `"shoulder_lift"` (id = 2)，零点位置改变了 -90 度，且方向与旧校准/代码相反。

```
action["shoulder_lift.pos"] = -(action["shoulder_lift.pos"] - 90)
```

对于 `"elbow_flex"` (id = 3)，零点位置与旧校准/代码相比改变了 -90 度。

```
action["elbow_flex.pos"] -= 90
```

为了使用角度归一化，我们将 `--robot.use_degrees` 选项设置为 `true`。

```
python examples/backward_compatibility/replay.py \
    --robot.type=so101_follower \
    --robot.port=/dev/tty.usbmodem5A460814411 \
    --robot.id=blue \
+   --robot.use_degrees=true \
    --dataset.repo_id=my_dataset_id \
    --dataset.episode=0
```

### 使用之前校准系统训练的策略

策略输出的动作格式与数据集相同 (`torch.Tensors`)。因此，应应用相同的转换。

为了找到这些转换，我们建议首先尝试使用上述章节的方法回放您策略所训练数据集的一个剧集。然后，在您的推理脚本中添加相同的转换（此处在 `record.py` 脚本中展示）

```
action_values = predict_action(
    observation_frame,
    policy,
    get_safe_torch_device(policy.config.device),
    policy.config.use_amp,
    task=single_task,
    robot_type=robot.robot_type,
    )
    action = {key: action_values[i].item() for i, key in enumerate(robot.action_features)}

+   action["shoulder_lift.pos"] = -(action["shoulder_lift.pos"] - 90)
+   action["elbow_flex.pos"] -= 90
    robot.send_action(action)
```

如果您有任何疑问或遇到迁移问题，欢迎在 [Discord](https://discord.gg/s3KuuzsPFb) 上提问

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/backwardcomp.mdx)
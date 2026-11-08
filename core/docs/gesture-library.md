<!-- 功能：已有动作库的安装、Agent 编排和执行语义。
Created on 2026-11-08; Updated on 2026-11-08
@author: https://github.com/Linmoqian -->

# 已有动作

来源为 [satyadevineni/gesture-commands](https://huggingface.co/datasets/satyadevineni/gesture-commands)，固定版本 `e253be78317eedcf221987653253de2a0e42701e`，Apache-2.0。运行 `python core/scripts/import_gesture_commands.py` 下载到本机 `core/data/gesture_library/`，原文件、SHA256 和版本保存在目录内，不提交大文件。运行时只读本地文件，不联网下载。

| ID | 名称 | 示例数 |
| --- | --- | --- |
| wave | 挥手 | 20 |
| spin | 旋转 | 20 |
| bow | 鞠躬 | 20 |
| unlabeled | 未命名动作，源标签 False | 20 |

`False` 的语义没有可靠标注，不命名成摇头或拒绝。80 段源动作保留；导入后约每 0.3 秒提取一个关键姿态。每轴相对第一帧的变化归一化，源变化小于 2 数值单位的轴置零，避免放大静态噪声。源角度单位及设备校准未经确认，因此不提供源绝对角度直放。

## Agent 工具

- `gesture_list()` 查询来源、四类动作及示例数。
- `gesture_play(actions=["wave","bow","wave"], target="simulation", amplitude_deg=15, variant=0)` 提交顺序程序。列表允许重复，示例编号从 0 开始，每段结束平滑回到编排起始姿态。
- `gesture_status(program_id)` 查询后台任务实际状态与日志。
- `gesture_stop(program_id)` 请求停止，随后查询终态。

`amplitude_deg` 是每轴相对编排起始姿态的最大变化，旋转动作并不保证转一整圈。所有关键姿态先按本机限位预检；越界报错，不静默裁剪。不需要训练。任务提交成功不代表画面、语义或真实任务已验收。

仿真按源时间间隔插值更新模型，含接口调用开销，不保证严格实时。真机 `target="serial:COM17"` 复用当前配置、编码器坐标转换和 HardwareClient，每个关键姿态发送最终位置并等实测到位，因此不会保持原 30 FPS 时序；正常结束或停止沿现有释放流程返回本次使能起始姿态并失能。程序清理由已有 ProgramWorker 托管，不能把发起停止当作失能已完成。

普通 Agent 与器灵都注册上述工具。器灵只能操作绑定目标；真机未启用运动时不暴露 gesture_play。Agent 先查库再编排，状态查询区分运行与完成；用户明确要求可见积木时继续使用积木编辑工具，不能以后台任务冒充已修改工作区。

本次验证包含真实 MCP 工具发现和查询、仿真 wave→bow 编排；没有运行导入动作到真机，尚未验收动作语义和真机观感。

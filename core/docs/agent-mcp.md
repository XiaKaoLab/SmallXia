# Agent 的模型、RL 与积木 MCP

Created on 2026-11-01; Updated on 2026-11-02
@author: https://github.com/Linmoqian

已在现有桌面 Agent 中启用标准 MCP stdio 客户端。Agent 使用 base Python 启动 `xiaoxia_core.mcp.server`，通过 initialize、tools/list 和 tools/call 发现并执行工具；工具再访问本机模型、强化学习或积木命令 HTTP API。

链路：聊天 → Responses 工具调用 → MCP 客户端 → MCP stdio 服务 → table 模型 API → 显示模型。

| 工具 | 功能 |
|---|---|
| `table_get_state` | GET `/api/v1/robots/table/state`，读取显示目标 |
| `table_get_limits` | 读取 table SO101 URDF 六轴弧度范围 |
| `table_move_joints` | POST `/api/v1/robots/table/motions`，发送完整六轴目标 |

运动工具只接受六个具名角度参数，没有 URL、串口或 robot_id 参数，目标固定为本机 table 模型。API 令牌只从环境读取，不放入工具参数或模型提示。未提供实机运动工具。积木程序可启动已有只读真机采集，但仍需匹配的设备身份、校准与本地配置。

先按 [运动 API](motion-api.md) 启动模型服务，再启动 table。启动桌面的进程需继承 `OPENAI_API_KEY`、`OPENAI_MODEL` 和与模型服务一致的 `XIAOXIA_MOTION_TOKEN`。原有 `OPENAI_BASE_URL` 可继续使用，但对应提供商需要支持 Responses 流式 function calling。MCP 服务由 Agent 自动启动和释放，不必手动运行。

可在聊天中输入：“读取模型状态和限位，然后把 shoulder_pan 调整到 0.2 rad，其他轴保持当前目标。”

聊天工具卡片沿用现有 `tool_started`、`tool_completed` 事件，显示执行中、完成或失败。工具输出通过 function_call_output 回传模型，文本继续流式输出。最多执行 8 轮，最后一轮禁止继续请求工具。工具错误会返回模型；不得将错误表述为成功或将 accepted 表述为实际渲染到位。历史会话仍保存用户/助手文本，工具过程仅在当次流中展示，尚未单独持久化。

普通 `OpenAILLM` 默认保持文本模式；桌面 bridge 和 Agent CLI 默认启用 MCP，CLI 可用 `--no-mcp` 关闭。其他 Python 调用方可使用 `OpenAILLM(config, enable_mcp=True)`。协议实现参考 [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) 和 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。

## RL 工具

RL 工具复用 ReinforcementClient，不在 MCP 内重新实现算法：

- rl_capabilities、rl_list_sessions、rl_get_session：执行范围和会话查询。
- rl_create_session、rl_step、rl_reset：创建会话、显式执行 table 模型步、开启新 episode。
- rl_intervene、rl_feedback、rl_label_reward：接管、用户明确标注的成功/失败和视觉奖励标签。
- rl_start_learner、rl_start_actor、rl_predict、rl_train_reward：后台 SAC 学习器、模型执行者、非执行预测和奖励训练。
- rl_get_job、rl_stop_job、rl_stop_session：状态、停止任务和停止整个会话。

创建会话不会自动训练/运动，任务返回不代表完成；状态与结果以 RL API 为准。动作空间是当前 table 的六关节归一化增量，不是实机末端空间。人工标签必须来自用户，不能由 LLM 臆测。

`rl_train_ball(num_envs=4, rounds=100, device="cpu")` 启动拿取小球的独立 MuJoCo 环境与共享 SAC 学习器；轮数按每个环境计算。任务 ID 可通过 `rl_get_job` 查询分数、回合与进度，通过 `rl_stop_job` 停止。积木类型 `table_policy_rl_ball` 使用 NUM_ENVS、ROUNDS、DEVICE 字段；启动后中间顶部显示训练面板。仅显式要求训练时调用，不把启动成功表述为已学会抓球。

## 积木工具

新增12个 blocks_ 工具：blocks_catalog、blocks_list、blocks_create、blocks_set_fields、blocks_move、blocks_connect、blocks_remove、blocks_clear、blocks_export、blocks_import、blocks_run、blocks_command_status。

catalog 返回六个分类和可用类型；list 返回 ID、字段、坐标。connect 用父/子 ID 与 input_name 连接命名输入，input_name 为空连接下一条语句。导出/导入保留 version=2 的变量和嵌套连接，并兼容旧 version=1 导入。

链路：MCP → 本机命令队列 → 当前 Tauri WebView 的 BlocksControlBridge → 现有工作区管理器/运行函数 → 回执。命令 API 使用同一令牌，页面通过既有 Tauri/Python 桥长轮询，令牌不进入浏览器。没有任意 JavaScript、CDP、URL 或 Python 源码执行参数。

每条命令只投递一次，8秒有效。未投递时过期为 expired，已投递但未确认时为 unknown；工具超时不重发。用 blocks_command_status 查询原命令，或读取工作区确认实际状态。窗口关闭、未就绪或重载时不能声称操作成功。服务重启会丢失未完成命令，需先重新读取工作区。

编辑、连接、导入不自动运行；set_fields 不触发滑杆发送。blocks_run 调用当前工作区最新程序，沿用隐藏的 base Python 与现有运行锁、错误输出。程序运行中不允许 MCP 修改工作区。只有用户要求运行时才执行；删除/清空/替换前应先读取或导出备份。

积木桥在正式 Tauri 窗口也挂载，不依赖开发调试端口。原 window.tableDebug 仍只由开发环境暴露。聊天卡片继续使用原 tool_started/tool_completed 事件显示过程，没有单独建立另一套 Agent。

## 本次检查

首次接入时实际 stdio 工具发现得到31个工具：3个原模型工具、16个 RL 工具、12个积木工具。通过 MCP 查询 RL 能力、读取六分类目录，并创建 false 条件及条件分支、连接输入、导出 version=2 后删除本次创建的积木。未修改原有积木，未运行程序、训练、运动或 OpenAI API 请求。

本次增加 rl_train_ball，未升级 MCP SDK。小球环境已做两个独立状态的单步检查和一次 SAC 参数更新，TypeScript 静态检查通过；未执行完整回合训练、真实 OpenAI 调用或实机动作，未构建桌面。

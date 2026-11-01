# Agent 的 table 模型 MCP

已在现有桌面 Agent 中启用标准 MCP stdio 客户端。Agent 使用 base Python 启动 `xiaoxia_core.mcp.server`，通过 initialize、tools/list 和 tools/call 发现并执行工具；工具再访问本机模型 HTTP API。

链路：聊天 → Responses 工具调用 → MCP 客户端 → MCP stdio 服务 → table 模型 API → 显示模型。

| 工具 | 功能 |
|---|---|
| `table_get_state` | GET `/api/v1/robots/table/state`，读取显示目标 |
| `table_get_limits` | 读取 table SO101 URDF 六轴弧度范围 |
| `table_move_joints` | POST `/api/v1/robots/table/motions`，发送完整六轴目标 |

运动工具只接受六个具名角度参数，没有 URL、串口或 robot_id 参数，目标固定为本机 table 模型。API 令牌只从环境读取，不放入工具参数或模型提示。未提供实机控制工具。

先按 [运动 API](motion-api.md) 启动模型服务，再启动 table。启动桌面的进程需继承 `OPENAI_API_KEY`、`OPENAI_MODEL` 和与模型服务一致的 `XIAOXIA_MOTION_TOKEN`。原有 `OPENAI_BASE_URL` 可继续使用，但对应提供商需要支持 Responses 流式 function calling。MCP 服务由 Agent 自动启动和释放，不必手动运行。

可在聊天中输入：“读取模型状态和限位，然后把 shoulder_pan 调整到 0.2 rad，其他轴保持当前目标。”

聊天工具卡片沿用现有 `tool_started`、`tool_completed` 事件，显示执行中、完成或失败。工具输出通过 function_call_output 回传模型，文本继续流式输出。最多执行 8 轮，最后一轮禁止继续请求工具。工具错误会返回模型；不得将错误表述为成功或将 accepted 表述为实际渲染到位。历史会话仍保存用户/助手文本，工具过程仅在当次流中展示，尚未单独持久化。

普通 `OpenAILLM` 默认保持文本模式；桌面 bridge 和 Agent CLI 默认启用 MCP，CLI 可用 `--no-mcp` 关闭。其他 Python 调用方可使用 `OpenAILLM(config, enable_mcp=True)`。协议实现参考 [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) 和 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。

本次安装 MCP SDK 1.30.0 至现有 Conda base，并更新其要求的 Pydantic、pywin32 等依赖。已完成标准 stdio 初始化、工具发现和连接退出，确认三个工具均可发现；另完成 Python 语法和 Git 差异检查。未执行模型运动、OpenAI 调用、桌面构建或视觉联动验证。安装器仍报告 base 已有的 LeRobot/diffusers、LightX2V/torch、OSAM/onnxruntime 和 Streamlit 依赖冲突，未在本次扩大处理范围。

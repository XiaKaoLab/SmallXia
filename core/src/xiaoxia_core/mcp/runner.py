"""执行 Responses 流式工具循环，经 MCP 调用模型、强化学习与积木工具。
Created on 2026-11-01; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

import json

from ..llm.messages import LLMStreamEvent
from .client import TableMCPClient


def stream_with_mcp(llm, messages, instructions):
    inputs = list(llm._input(messages))
    text = ""
    input_tokens = output_tokens = 0
    guidance = ("持续循环调用工具完成当前请求，根据结果决定下一步，完成后回复。步骤之间简短说明意图。不要密集轮询后台任务；重复失败时停止说明，不得重试未知结果的动作。""\n直接运动工具只控制 table 显示模型。运动前读取模型状态和限位。"
                "只有用户请求运动时才发送动作。工具错误或超时不得自动重试运动；"
                "必须如实说明失败。accepted 仅为目标接收，不得声称渲染到位。"
                "RL 工具复用现有 API：创建会话不代表训练；启动学习器、执行者或奖励训练前必须有用户对应意图。"
                "不得编造成功/失败标签；后台任务需查询状态，succeeded 也不代表任务成功率通过。"
                "积木操作先读取目录和工作区；修改/连接不自动运行；只有用户明确要求运行才调用 blocks_run。"
                "替换快照或批量改动前先导出备份；积木命令超时可能已生效，应查询回执或工作区，禁止重发。"
                "blocks_run 返回 program.id 仅表示程序已提交，使用 blocks_program_status 确认完成，停止使用 blocks_program_stop。"
                "积木程序可能包含真机控制；只有用户明确请求真机运动时，才创建或运行启用真机控制积木。"
                "真机控制及只读采集遵守既有身份、校准和已验证坐标配置；不得修改 verified 或身份字段绕过检查。")
    with TableMCPClient() as mcp:
        for round_index in range(64):
            with llm._client.responses.stream(
                model=llm.config.model, input=inputs, instructions=instructions + guidance,
                tools=mcp.tools, parallel_tool_calls=False,
                include=["reasoning.encrypted_content"],
                tool_choice="none" if round_index == 63 else "auto",
                max_output_tokens=llm.config.max_output_tokens, store=False,
            ) as stream:
                for event in stream:
                    if event.type == "response.output_text.delta":
                        text += event.delta
                        yield LLMStreamEvent("delta", delta=event.delta)
                    elif event.type == "error":
                        raise RuntimeError("LLM 工具流错误")
                response = stream.get_final_response()
            if response.status != "completed":
                raise RuntimeError(f"LLM 工具轮次未完成: {response.status}")
            if response.usage:
                input_tokens += response.usage.input_tokens
                output_tokens += response.usage.output_tokens
            inputs.extend(item.model_dump(mode="json", exclude_none=True) for item in response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                from ..llm.client_types import LLMResult
                if not text.strip():
                    raise RuntimeError("LLM 未返回最终文本")
                yield LLMStreamEvent("completed", result=LLMResult(
                    text, response.id, response.model, input_tokens, output_tokens))
                return
            for call in calls:
                yield LLMStreamEvent("tool_started", call_id=call.call_id, name=call.name)
                failed = False
                try:
                    arguments = json.loads(call.arguments)
                    if not isinstance(arguments, dict):
                        raise ValueError("工具参数必须为对象")
                    result = mcp.call(call.name, arguments)
                    failed = bool(result.get("isError"))
                except Exception as error:
                    failed = True
                    result = {"isError": True, "error": type(error).__name__,
                              "message": "工具调用失败；如为运动请求，结果可能未知，请先读取状态，勿自动重试"}
                output = json.dumps(result, ensure_ascii=False)
                yield LLMStreamEvent("tool_completed", call_id=call.call_id,
                                     output=output, failed=failed)
                inputs.append({"type": "function_call_output", "call_id": call.call_id, "output": output})
    raise RuntimeError("超出 Agent 工具轮数限制")

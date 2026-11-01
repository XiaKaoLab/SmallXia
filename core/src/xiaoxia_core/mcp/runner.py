"""执行 Responses 流式工具循环，经 MCP 调用模型运动 API。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import json

from ..llm.messages import LLMStreamEvent
from .client import TableMCPClient


def stream_with_mcp(llm, messages, instructions):
    inputs = list(llm._input(messages))
    text = ""
    input_tokens = output_tokens = 0
    guidance = ("\n工具只控制 table 显示模型，不是实机。运动前读取模型状态和限位。"
                "只有用户请求运动时才发送动作。工具错误或超时不得自动重试运动；"
                "必须如实说明失败。accepted 仅为目标接收，不得声称渲染到位。")
    with TableMCPClient() as mcp:
        for round_index in range(8):
            with llm._client.responses.stream(
                model=llm.config.model, input=inputs, instructions=instructions + guidance,
                tools=mcp.tools, parallel_tool_calls=False,
                include=["reasoning.encrypted_content"],
                tool_choice="none" if round_index == 7 else "auto",
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

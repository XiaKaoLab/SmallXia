"""定义多轮消息和流式 LLM 事件。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from dataclasses import dataclass
from typing import Literal

from .client_types import LLMResult


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["user", "assistant"]
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant") or not self.content.strip():
            raise ValueError("消息必须是非空的 user/assistant 文本")


@dataclass(frozen=True)
class LLMStreamEvent:
    type: Literal["delta", "completed", "tool_started", "tool_completed"]
    delta: str = ""
    result: LLMResult | None = None

    call_id: str = ""
    name: str = ""
    output: str = ""
    failed: bool = False

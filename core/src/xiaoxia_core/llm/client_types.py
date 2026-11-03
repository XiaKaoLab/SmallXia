"""LLM 完整结果数据类型。
Created on 2026-11-01; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResult:
    text: str
    response_id: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    choices: tuple[str, ...] = ()

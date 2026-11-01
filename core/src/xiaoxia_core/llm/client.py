"""通过 OpenAI Responses API 实现可替换的 LLM 文本生成接口。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import TracebackType

from openai import OpenAI

from .config import LLMConfig


@dataclass(frozen=True)
class LLMResult:
    text: str
    response_id: str
    model: str
    input_tokens: int | None
    output_tokens: int | None


class LLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, instructions: str = "") -> LLMResult:
        """生成文本；调用失败应抛出异常。"""


class OpenAILLM(LLM):
    def __init__(self, config: LLMConfig, *, api_key: str | None = None) -> None:
        self.config = config
        # SDK 默认读取 OPENAI_API_KEY。构造客户端不会发送模型请求。
        self._client = OpenAI(
            api_key=api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def generate(self, prompt: str, *, instructions: str = "") -> LLMResult:
        if not prompt.strip():
            raise ValueError("prompt 不能为空")
        response = self._client.responses.create(
            model=self.config.model,
            input=prompt,
            instructions=instructions,
            max_output_tokens=self.config.max_output_tokens,
            store=False,
        )
        if response.status != "completed":
            raise RuntimeError(
                f"LLM 响应未完成: status={response.status}, id={response.id}"
            )
        text = response.output_text
        if not text.strip():
            raise RuntimeError(f"LLM 未返回文本: id={response.id}")
        usage = response.usage
        return LLMResult(
            text=text,
            response_id=response.id,
            model=response.model,
            input_tokens=usage.input_tokens if usage is not None else None,
            output_tokens=usage.output_tokens if usage is not None else None,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OpenAILLM":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

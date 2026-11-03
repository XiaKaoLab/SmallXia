"""通过 OpenAI Responses API 实现可替换的 LLM 文本生成接口。
Created on 2026-11-01; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from types import TracebackType

from openai import OpenAI
from openai.types.responses import Response, ResponseInputParam

from .client_types import LLMResult
from .config import LLMConfig
from .messages import LLMMessage, LLMStreamEvent


class LLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, instructions: str = "") -> LLMResult:
        """生成文本；调用失败应抛出异常。"""

    def stream_messages(
        self, messages: Sequence[LLMMessage], *, instructions: str = ""
    ) -> Iterator[LLMStreamEvent]:
        raise NotImplementedError("当前 LLM 未实现多轮流式调用")


class OpenAILLM(LLM):
    def __init__(self, config: LLMConfig, *, api_key: str | None = None, enable_mcp: bool = False, mcp_profile: str = "default") -> None:
        from ..environment import EnvironmentSettings
        EnvironmentSettings.load()
        self.config = config
        self.enable_mcp = enable_mcp
        self.mcp_profile = mcp_profile
        # SDK 默认读取 OPENAI_API_KEY。构造客户端不会发送模型请求。
        self._client = OpenAI(
            api_key=api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def generate(self, prompt: str, *, instructions: str = "") -> LLMResult:
        return self.generate_messages([LLMMessage("user", prompt)], instructions=instructions)

    @staticmethod
    def _input(messages: Sequence[LLMMessage]) -> ResponseInputParam:
        if not messages:
            raise ValueError("消息列表不能为空")
        return [{"role": message.role, "content": message.content} for message in messages]

    def generate_messages(
        self, messages: Sequence[LLMMessage], *, instructions: str = ""
    ) -> LLMResult:
        response = self._client.responses.create(
            model=self.config.model,
            input=self._input(messages),
            instructions=instructions,
            max_output_tokens=self.config.max_output_tokens,
            store=False,
        )
        return self._result(response)

    @staticmethod
    def _result(response: Response) -> LLMResult:
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

    def stream_messages(
        self, messages: Sequence[LLMMessage], *, instructions: str = ""
    ) -> Iterator[LLMStreamEvent]:
        if self.enable_mcp:
            from ..mcp.runner import stream_with_mcp
            yield from stream_with_mcp(self, messages, instructions)
            return
        from .response_round import ResponseRound
        response = yield from ResponseRound(self).stream(
            model=self.config.model, input=self._input(messages), instructions=instructions,
        )
        if response.status != 'completed':
            raise RuntimeError(f"模型回复未完成: {response.status}")
        result = self._result(response)
        yield LLMStreamEvent("completed", result=result)

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

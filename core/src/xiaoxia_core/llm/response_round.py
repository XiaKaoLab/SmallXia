"""功能：有限恢复未输出文字的模型流请求，保留既有工具回执且不重放工具。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from openai import APIConnectionError, APIStatusError
from .messages import LLMStreamEvent


class ResponseRound:
    def __init__(self, llm):
        self.llm = llm

    def stream(self, **request):
        emitted = False
        budget = self.llm.config.max_output_tokens
        for attempt in range(2):
            try:
                client = self.llm._client.with_options(max_retries=0)
                if attempt or not getattr(self.llm.config, "stream_responses", True):
                    # SSE终止事件缺失时改用普通响应；当前轮工具尚未执行，不重放历史工具。
                    response = client.responses.create(**request, max_output_tokens=budget, store=False)
                    reason = getattr(getattr(response, 'incomplete_details', None), 'reason', None)
                    if response.status == 'incomplete' and reason == 'max_output_tokens' and attempt == 0 and budget < 8192:
                        budget = min(8192, max(4096, budget * 2))
                        continue
                    if response.status == 'completed' and response.output_text:
                        emitted = True
                        yield LLMStreamEvent('delta', delta=response.output_text)
                    return response
                with client.responses.stream(
                    **request, max_output_tokens=budget, store=False,
                ) as stream:
                    for event in stream:
                        if event.type == 'response.output_text.delta':
                            emitted = True
                            yield LLMStreamEvent('delta', delta=event.delta)
                        elif event.type == 'error':
                            raise RuntimeError('模型流返回错误，当前请求未完成')
                    response = stream.get_final_response()
            except (APIConnectionError, APIStatusError) as error:
                transient = isinstance(error, APIConnectionError) or error.status_code == 429 or error.status_code >= 500
                if attempt == 0 and transient and not emitted:
                    continue
                raise
            except RuntimeError as error:
                if "Didn't receive a `response.completed` event" in str(error):
                    if attempt == 0 and not emitted:
                        continue
                    raise RuntimeError('模型流提前结束，未收到完整回复；本轮工具不会自动重做') from error
                raise
            reason = getattr(getattr(response, 'incomplete_details', None), 'reason', None)
            if response.status == 'incomplete' and reason == 'max_output_tokens' and not emitted and attempt == 0 and budget < 8192:
                budget = min(8192, max(4096, budget * 2))
                continue
            return response

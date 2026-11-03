"""组合消息、技能与流式 LLM，完整成功后原子保存一轮对话。
Created on 2026-11-01; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

from collections.abc import Iterator, Sequence
from contextlib import closing
from dataclasses import dataclass
from threading import Lock
from typing import Literal

from ..llm import LLM, LLMMessage, LLMResult
from .sessions import SessionStore
from .skills import SkillRegistry
from .transcript import AgentTranscript
from .memory import AgentMemory


@dataclass(frozen=True)
class AgentEvent:
    type: Literal["started", "skill_loaded", "delta", "completed", "tool_started", "tool_completed"]
    session_id: str
    delta: str = ""
    skill: str = ""
    result: LLMResult | None = None
    call_id: str = ""
    name: str = ""
    output: str = ""
    failed: bool = False


class SimpleAgent:
    def __init__(
        self, llm: LLM, sessions: SessionStore, skills: SkillRegistry,
        instructions: str = "你是小虾台助手。使用简体中文，明确区分建议、仿真和实机事实。",
        max_context_turns: int = 20,
        max_skill_characters: int = 65_536,
    ) -> None:
        if max_context_turns < 1 or max_skill_characters < 1:
            raise ValueError("上下文轮数和技能长度上限必须为正数")
        self.llm, self.sessions, self.skills = llm, sessions, skills
        self.instructions = instructions
        self.max_context_turns = max_context_turns
        self.max_skill_characters = max_skill_characters
        self._busy = Lock()
        self.memory = AgentMemory(sessions, llm)

    def stream(
        self, session_id: str, text: str, *, skill_names: Sequence[str] = ()
    ) -> Iterator[AgentEvent]:
        user = LLMMessage("user", text)
        if not self._busy.acquire(blocking=False):
            raise RuntimeError("当前 Agent 正在处理另一轮消息")
        try:
            snapshot = self.sessions.read(session_id)
            names = tuple(dict.fromkeys(skill_names))
            sections = [f"## Skill: {name}\n{self.skills.load(name)}" for name in names]
            if sum(map(len, sections)) > self.max_skill_characters:
                raise ValueError("所选技能指令过长，请减少技能数量")
            yield AgentEvent("started", session_id)
            self.memory.remember(text)
            memory, history = self.memory.context(snapshot, self.max_context_turns)
            instructions = "\n\n".join([self.instructions, memory, *sections])
            messages = [*history, user]
            transcript = AgentTranscript()
            for name in names:
                transcript.activity(f'skill-{name}', name, 'skill', 'completed', '技能指令已加载')
                yield AgentEvent("skill_loaded", session_id, skill=name)
            result: LLMResult | None = None
            with closing(self.llm.stream_messages(messages, instructions=instructions)) as stream:
                for event in stream:
                    if event.type == "delta":
                        if result is not None:
                            raise RuntimeError("LLM 完成事件后出现文本增量")
                        transcript.text(event.delta)
                        yield AgentEvent("delta", session_id, delta=event.delta)
                    elif event.type in ("tool_started", "tool_completed"):
                        if event.type == 'tool_started':
                            transcript.activity(event.call_id, event.name, 'tool')
                        else:
                            transcript.complete_tool(event.call_id, event.output, event.failed)
                        yield AgentEvent(event.type, session_id, call_id=event.call_id,
                                         name=event.name, output=event.output, failed=event.failed)
                    elif event.type == "completed":
                        if result is not None or event.result is None:
                            raise RuntimeError("LLM 完成事件缺失结果或重复")
                        result = event.result
            if result is None:
                raise RuntimeError("LLM 流在完成前结束，本轮未保存")
            self.sessions.append_turn(snapshot, user, LLMMessage("assistant", result.text), presentation=transcript.finish(result.text))
            yield AgentEvent("completed", session_id, result=result)
        finally:
            self._busy.release()

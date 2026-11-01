"""为 Tauri 提供单请求 JSONL 桥接，复用会话、技能与 Agent 流。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import json
import os
import sys
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from ..llm import LLMConfig, OpenAILLM
from .runtime import SimpleAgent
from .sessions import SessionStore
from .skills import SkillRegistry


class DesktopBridge:
    def __init__(self, directory: Path) -> None:
        self.sessions = SessionStore(directory / "data" / "agent.sqlite3")
        self.skills = SkillRegistry(directory / "skills")

    @staticmethod
    def emit(event: dict) -> None:
        print(json.dumps(event, ensure_ascii=False), flush=True)

    def handle(self, request: dict) -> None:
        action = request.get("action")
        if action == "bootstrap":
            sessions = []
            for session_id in self.sessions.list_sessions():
                messages = self.sessions.read(session_id).messages
                title = messages[0].content[:48] if messages else "新对话"
                sessions.append({"id": session_id, "title": title})
            self.emit({"type": "data", "data": {
                "sessions": sessions,
                "skills": [{"name": skill.name, "description": skill.description}
                           for skill in self.skills.list()],
                "model": os.environ.get("OPENAI_MODEL", ""),
                "configured": bool(os.environ.get("OPENAI_MODEL") and os.environ.get("OPENAI_API_KEY")),
            }})
        elif action == "create":
            self.emit({"type": "data", "data": {"id": self.sessions.create()}})
        elif action == "history":
            snapshot = self.sessions.read(request["session_id"])
            self.emit({"type": "data", "data": {
                "messages": [asdict(message) for message in snapshot.messages]
            }})
        elif action == "clear":
            self.sessions.clear(request["session_id"])
            self.emit({"type": "data", "data": {"cleared": True}})
        elif action == "run_program":
            from ..communication.program_runner import PythonProgramRunner
            self.emit({"type": "data", "data": PythonProgramRunner().run(request.get("source"))})
        elif action == "run":
            with OpenAILLM(LLMConfig.from_env(), enable_mcp=True) as llm:
                agent = SimpleAgent(llm, self.sessions, self.skills)
                with closing(agent.stream(
                    request["session_id"], request["text"],
                    skill_names=request.get("skill_names", []),
                )) as events:
                    for event in events:
                        self.emit(asdict(event))
        else:
            raise ValueError("未知桌面请求")


def main() -> None:
    # Windows 管道默认编码不一定是 UTF-8，与 Rust/前端明确统一。
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        request = json.loads(sys.stdin.readline())
        if not isinstance(request, dict):
            raise ValueError("桌面请求必须为对象")
        DesktopBridge(Path.cwd()).handle(request)
    except Exception as error:
        DesktopBridge.emit({"type": "error", "message": str(error)})
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

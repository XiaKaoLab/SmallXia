"""简单 Agent 的命令行会话与流式交互入口。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import argparse
import sys
from contextlib import closing
from pathlib import Path

from ..llm import LLMConfig, OpenAILLM
from .runtime import SimpleAgent
from .sessions import SessionStore
from .skills import SkillRegistry


class AgentConsole:
    def __init__(self, agent: SimpleAgent, session_id: str | None = None) -> None:
        self.agent = agent
        self.session_id = session_id or agent.sessions.create()
        agent.sessions.read(self.session_id)
        self.active_skills: tuple[str, ...] = ()

    def _command(self, text: str) -> bool:
        command, _, argument = text.partition(" ")
        argument = argument.strip()
        match command:
            case "/quit":
                return False
            case "/new":
                self.session_id = self.agent.sessions.create()
                print(f"新会话: {self.session_id}")
            case "/sessions":
                print("\n".join(self.agent.sessions.list_sessions()))
            case "/resume":
                self.agent.sessions.read(argument)
                self.session_id = argument
                print(f"恢复会话: {self.session_id}")
            case "/clear":
                self.agent.sessions.clear(self.session_id)
                print("当前会话消息已清空")
            case "/history":
                for message in self.agent.sessions.read(self.session_id).messages:
                    print(f"{message.role}: {message.content}")
            case "/skills":
                self.agent.skills.refresh()
                for skill in self.agent.skills.list():
                    print(f"{skill.name}: {skill.description}")
            case "/skill":
                names = () if argument == "off" else tuple(dict.fromkeys(argument.split()))
                for name in names:
                    self.agent.skills.load(name)
                self.active_skills = names
                print(f"当前技能: {', '.join(names) or '无'}")
            case _:
                print("命令: /new /sessions /resume ID /clear /history /skills /skill 名称 /skill off /quit")
        return True

    def run(self) -> None:
        print(f"会话: {self.session_id}，输入 /help 查看命令")
        while True:
            try:
                text = input("工程师> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not text:
                continue
            try:
                if text.startswith("/"):
                    if not self._command(text):
                        return
                    continue
                with closing(self.agent.stream(
                    self.session_id, text, skill_names=self.active_skills
                )) as events:
                    for event in events:
                        if event.type == "delta":
                            print(event.delta, end="", flush=True)
                        elif event.type == "skill_loaded":
                            print(f"[技能: {event.skill}]")
                        elif event.type == "completed":
                            print()
            except KeyboardInterrupt:
                print("\n本轮已中断")
            except Exception as error:
                print(f"\n处理失败: {error}", file=sys.stderr)


def main() -> None:
    core = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="小虾台简单 Agent")
    parser.add_argument("--database", type=Path, default=core / "data" / "agent.sqlite3")
    parser.add_argument("--skills", type=Path, default=core / "skills")
    parser.add_argument("--session", default=None)
    args = parser.parse_args()
    try:
        skills = SkillRegistry(args.skills)
        sessions = SessionStore(args.database)
        with OpenAILLM(LLMConfig.from_env()) as llm:
            AgentConsole(SimpleAgent(llm, sessions, skills), args.session).run()
    except Exception as error:
        parser.exit(1, f"Agent 启动失败: {error}\n")

"""使用 SQLite 管理会话与完整轮次，乐观锁防止覆盖并发修改。
Created on 2026-11-01; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

import sqlite3
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ..llm import LLMMessage


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: str
    revision: int
    messages: tuple[LLMMessage, ...]


class SessionStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, id);
                CREATE TABLE IF NOT EXISTS agent_memory (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS message_presentations (
                    message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                    presentation TEXT NOT NULL
                );
            """)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def memory(self, key: str) -> str:
        with self._connection() as db:
            row = db.execute("SELECT value FROM agent_memory WHERE key = ?", (key,)).fetchone()
        return row[0] if row else ""

    def save_memory(self, key: str, value: str) -> None:
        with self._connection() as db:
            db.execute("INSERT INTO agent_memory(key, value) VALUES (?, ?) "
                       "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))

    def create(self) -> str:
        session_id = uuid4().hex
        with self._connection() as db:
            db.execute("INSERT INTO sessions(id) VALUES (?)", (session_id,))
        return session_id

    def list_sessions(self) -> tuple[str, ...]:
        with self._connection() as db:
            return tuple(row[0] for row in db.execute("SELECT id FROM sessions ORDER BY rowid DESC"))

    def read(self, session_id: str) -> SessionSnapshot:
        with self._connection() as db:
            rows = db.execute(
                """SELECT s.revision, m.role, m.content FROM sessions s
                   LEFT JOIN messages m ON m.session_id = s.id
                   WHERE s.id = ? ORDER BY m.id""", (session_id,)
            ).fetchall()
        if not rows:
            raise KeyError(f"会话不存在: {session_id}")
        messages = tuple(LLMMessage(row[1], row[2]) for row in rows if row[1] is not None)
        return SessionSnapshot(session_id, rows[0][0], messages)

    def append_turn(
        self, snapshot: SessionSnapshot, user: LLMMessage, assistant: LLMMessage, *, presentation=None
    ) -> None:
        if user.role != "user" or assistant.role != "assistant":
            raise ValueError("完整轮次必须依次包含 user 和 assistant")
        with self._connection() as db:
            changed = db.execute(
                "UPDATE sessions SET revision = revision + 1 WHERE id = ? AND revision = ?",
                (snapshot.session_id, snapshot.revision),
            ).rowcount
            if changed != 1:
                raise RuntimeError("会话已被其他调用修改，本轮回答未保存")
            for message in (user, assistant):
                cursor = db.execute('INSERT INTO messages(session_id, role, content) VALUES (?, ?, ?)',
                    (snapshot.session_id, message.role, message.content))
                if message.role == 'assistant' and presentation is not None:
                    db.execute('INSERT INTO message_presentations(message_id, presentation) VALUES (?, ?)',
                        (cursor.lastrowid, json.dumps(presentation, ensure_ascii=False)))

    def read_display(self, session_id):
        self.read(session_id)  # 同样校验会话存在。
        with self._connection() as db:
            rows = db.execute('''SELECT m.role, m.content, p.presentation FROM messages m
                LEFT JOIN message_presentations p ON p.message_id = m.id
                WHERE m.session_id = ? ORDER BY m.id''', (session_id,)).fetchall()
        return [dict(role=role, content=content, **(json.loads(presentation) if presentation else {}))
                for role, content, presentation in rows]

    def clear(self, session_id: str) -> None:
        with self._connection() as db:
            changed = db.execute(
                "UPDATE sessions SET revision = revision + 1 WHERE id = ?", (session_id,)
            ).rowcount
            if changed != 1:
                raise KeyError(f"会话不存在: {session_id}")
            db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            db.execute("DELETE FROM agent_memory WHERE key = ?", (f"summary:{session_id}",))

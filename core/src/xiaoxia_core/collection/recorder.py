"""以 JSONL 记录 episode 中的观测和可选示教动作。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import json
from dataclasses import asdict
from pathlib import Path
from types import TracebackType
from typing import TextIO

from ..contracts import Action, Observation


class EpisodeRecorder:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._stream: TextIO | None = None

    def open(self) -> None:
        if self._stream is not None:
            raise RuntimeError("episode 已打开")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("x", encoding="utf-8")

    def append(self, observation: Observation, action: Action | None = None) -> None:
        if self._stream is None:
            raise RuntimeError("请先打开 episode")
        record = {
            "schema_version": 1,
            "observation": asdict(observation),
            "action": asdict(action) if action is not None else None,
        }
        self._stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        self._stream.flush()

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def __enter__(self) -> "EpisodeRecorder":
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

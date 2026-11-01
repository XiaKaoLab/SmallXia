"""发现 SKILL.md 元数据，并显式加载所选技能指令。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path


class SkillRegistry:
    def __init__(self, directory: Path, max_bytes: int = 65_536) -> None:
        self.directory = Path(directory).resolve()
        if max_bytes < 1:
            raise ValueError("技能大小上限必须为正数")
        self.max_bytes = max_bytes
        self._skills: dict[str, Skill] = {}
        self.refresh()

    def _read(self, path: Path) -> str:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.directory):
            raise ValueError("技能文件超出技能目录")
        with resolved.open("rb") as stream:
            raw = stream.read(self.max_bytes + 1)
        if len(raw) > self.max_bytes:
            raise ValueError(f"技能文件过大: {path}")
        return raw.decode("utf-8-sig")

    @staticmethod
    def _parse(text: str) -> tuple[dict, str]:
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError("SKILL.md 必须包含 YAML frontmatter")
        end = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
        if end is None:
            raise ValueError("技能 frontmatter 未闭合")
        metadata = yaml.safe_load("\n".join(lines[1:end]))
        body = "\n".join(lines[end + 1:]).strip()
        if not isinstance(metadata, dict) or not body:
            raise ValueError("技能元数据或正文为空")
        return metadata, body

    def refresh(self) -> None:
        skills: dict[str, Skill] = {}
        if not self.directory.is_dir():
            raise FileNotFoundError(self.directory)
        for path in sorted(self.directory.glob("*/SKILL.md")):
            metadata, _ = self._parse(self._read(path))
            name, description = metadata.get("name"), metadata.get("description")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                raise ValueError(f"技能名称必须为小写字母数字和连字符: {path}")
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"技能缺少 description: {path}")
            if name in skills:
                raise ValueError(f"重复技能名称: {name}")
            skills[name] = Skill(name, description.strip(), path)
        self._skills = skills

    def list(self) -> tuple[Skill, ...]:
        return tuple(self._skills.values())

    def load(self, name: str) -> str:
        if name not in self._skills:
            raise KeyError(f"技能不存在: {name}")
        metadata, body = self._parse(self._read(self._skills[name].path))
        if metadata.get("name") != name:
            raise ValueError("技能名称已变化，请刷新技能目录")
        return body

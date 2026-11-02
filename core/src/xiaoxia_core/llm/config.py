"""从环境变量读取 LLM 配置，不在源码中保存密钥。
Created on 2026-11-01; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""

import os
from dataclasses import dataclass
from math import isfinite
from ..environment import EnvironmentSettings


@dataclass(frozen=True)
class LLMConfig:
    model: str
    base_url: str | None = None
    timeout: float = 60.0
    max_retries: int = 2
    max_output_tokens: int = 2048

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("请配置 OPENAI_MODEL 或指定模型名称")
        if not isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout 必须为有限正数")
        if self.max_retries < 0 or self.max_output_tokens < 1:
            raise ValueError("重试次数必须非负，输出 token 上限必须为正数")

    @classmethod
    def from_env(cls) -> "LLMConfig":
        EnvironmentSettings.load()
        return cls(
            model=os.environ.get("OPENAI_MODEL", "").strip(),
            base_url=os.environ.get("OPENAI_BASE_URL", "").strip() or None,
        )

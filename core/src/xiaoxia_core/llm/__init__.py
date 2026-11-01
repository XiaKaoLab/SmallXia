"""大语言模型调用模块公共接口。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from .client import LLM, LLMResult, OpenAILLM
from .config import LLMConfig

__all__ = ["LLM", "LLMConfig", "LLMResult", "OpenAILLM"]

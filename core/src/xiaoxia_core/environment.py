"""从固定工作区路径读取本地.env，保留启动进程显式传入的环境变量。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from pathlib import Path
from dotenv import load_dotenv


class EnvironmentSettings:
    @staticmethod
    def load() -> None:
        core = Path(__file__).resolve().parents[2]
        # 优先级：进程环境 > core/.env > 工作区根目录.env；不依赖启动目录。
        for path in (core / '.env', core.parent / '.env'):
            load_dotenv(path, override=False, encoding='utf-8-sig')

"""在现有 base Python 中执行 Blockly 生成的模型控制程序并返回输出。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import os
import subprocess
import sys


class PythonProgramRunner:
    def run(self, source: str) -> dict:
        if not isinstance(source, str) or not source.strip() or len(source) > 65536:
            raise ValueError("Python 程序为空或超过长度限制")
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        try:
            process = subprocess.run(
                [sys.executable, "-u", "-"], input=source, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=5,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **options,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Python 运行超时；目标可能已发送，请先检查模型状态") from None
        if process.returncode:
            raise RuntimeError((process.stderr or process.stdout or "Python 运行失败")[-8000:])
        return {"output": process.stdout[-8000:], "exit_code": process.returncode}

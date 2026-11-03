"""功能：解析聊天快捷命令，分离确定性上下文压缩与仿真训练请求。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""


class AgentCommands:
    @staticmethod
    def is_compact(text: str) -> bool:
        return text.strip() == '/压缩'

    @staticmethod
    def prompt(text: str) -> str:
        parts = text.strip().split(maxsplit=1)
        if not parts or parts[0] != '/训练':
            return text
        requirement = parts[1] if len(parts) > 1 else '拿取小球'
        return ('用户通过 /训练 明确要求启动仿真训练。仅使用现有仿真训练流程，不连接或操作真机。'
                '先读取能力并结合当前上下文选择参数，再实际提交训练任务；不能只给教程。'
                '提交后说明真实进度或任务状态，不密集轮询，不把提交当成完成，不承诺成功率。'
                '若补充要求明确包含真机操作或与当前仿真任务不兼容，先澄清，不擅自切换到真机或忽略用户要求。'
                f'本次补充要求：{requirement}')

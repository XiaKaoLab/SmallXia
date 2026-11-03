"""功能：用结构化问题和候选答案暂停 Agent，等待用户选择或自由回答。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""


class QuestionTool:
    definition = {
        'type': 'function', 'name': 'ask_user', 'strict': False,
        'description': '需要用户澄清目标、选择方案或补充必要信息时使用。提供一个自然问题和2–4个简短候选答案，用户仍可自由输入。调用后结束本轮等待回答，不替用户选择。普通结果回复不要强行提问。',
        'parameters': {'type': 'object', 'properties': {
            'question': {'type': 'string', 'description': '直接向用户提出的问题，最多300字'},
            'options': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 4,
                        'description': '互相可区分的简短回答，不含其他/自定义，最多80字每项'},
        }, 'required': ['question', 'options'], 'additionalProperties': False},
    }

    @staticmethod
    def parse(arguments: dict) -> tuple[str, tuple[str, ...]]:
        question, options = arguments.get('question'), arguments.get('options')
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 300:
            raise ValueError('问题需要1–300字')
        if not isinstance(options, list) or not 2 <= len(options) <= 4:
            raise ValueError('需要2–4个候选答案')
        if any(not isinstance(option, str) or not 1 <= len(option.strip()) <= 80 for option in options):
            raise ValueError('每个候选答案需要1–80字')
        choices = tuple(option.strip() for option in options)
        if len(set(choices)) != len(choices):
            raise ValueError('候选答案不能重复')
        return question.strip(), choices

"""记录回复文字与操作的真实事件顺序，仅用于展示，不加入模型上下文。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""


class AgentTranscript:
    def __init__(self):
        self.parts = []
        self.activities = []

    def text(self, delta):
        if not delta:
            return
        if self.parts and self.parts[-1]['type'] == 'text':
            self.parts[-1]['text'] += delta
        else:
            self.parts.append({'type': 'text', 'id': f'text-{len(self.parts)}', 'text': delta})

    def activity(self, identity, name, kind, status='running', output=''):
        self.activities.append({'id': identity, 'name': name, 'kind': kind, 'status': status, 'output': output})
        self.parts.append({'type': 'activity', 'id': identity})

    def complete_tool(self, identity, output, failed):
        for activity in self.activities:
            if activity['id'] == identity:
                activity.update(output=output, status='failed' if failed else 'completed')
                break

    def finish(self, text):
        streamed = ''.join(part['text'] for part in self.parts if part['type'] == 'text')
        if text.startswith(streamed):
            self.text(text[len(streamed):])
        return {'parts': self.parts, 'activities': self.activities}

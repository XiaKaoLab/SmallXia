"""功能：在积木等待或策略推理期间维持已有真机会话，不创建连接或重发动作。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from threading import Event, Thread
from ..blocks.workflow import BlockWorkflow


class ControlHeartbeat:
    def __init__(self, port):
        self.port = port
        self.closed = Event()
        self.thread = Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def run(self):
        while not self.closed.wait(.4):
            try:
                state = BlockWorkflow.http(f'hardware/arms/{self.port}')
                if state['status'] not in ('connecting', 'ready', 'moving'):
                    break
            except Exception:
                break

    def close(self):
        self.closed.set()

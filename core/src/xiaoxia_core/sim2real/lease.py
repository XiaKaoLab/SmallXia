"""器灵真机控制租约：模型等待期间维持心跳并发布实测角度，结束时释放控制。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from threading import Event,Thread
from ..blocks.workflow import BlockWorkflow


class HardwareLease:
    def __init__(self,port,node_id,name,emit):
        self.port=port;self.emit=emit;self.node_id=node_id;self.name=name
        self.stop=Event();self.thread=Thread(target=self.run,daemon=True)

    def start(self):self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:
                state=BlockWorkflow.http(f'hardware/arms/{self.port}')
                if state['status'] not in ('ready','moving'):break
                if state.get('feedback_age_ms',501)<=500:
                    self.emit({'qiling':{'type':'hardware_feedback','node_id':self.node_id,'spirit':self.name,
                        'target':f'serial:{self.port}','physical':True,'source':'hardware_feedback','unit':'rad',
                        'joint_positions':state['joint_positions'],'observed_at_ns':state.get('observed_at_ns'),
                        'feedback_age_ms':state['feedback_age_ms']}})
            except Exception:break  # 心跳失败不重发动作，由硬件控制看门狗释放。
            self.stop.wait(.4)

    def close(self):
        self.stop.set()
        BlockWorkflow.http(f'hardware/arms/{self.port}/stop',{})

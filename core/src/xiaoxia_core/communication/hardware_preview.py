"""功能：持续订阅真机反馈，按已确认本机配置建立只读连接，不使能、不刷新控制租约。
Created on 2026-11-04; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from time import sleep
from ..blocks.workflow import BlockWorkflow

class HardwarePreviewStream:
    @staticmethod
    def run(emit):
        state=BlockWorkflow.http('hardware/arms')
        if not state['sessions']:
            from pathlib import Path
            from ..imitation.workflows import HardwareWorkflow
            profile=Path(__file__).resolve().parents[3]/'configs/so100.local.yaml'
            if profile.exists():
                workflow=HardwareWorkflow(profile)
                port=workflow.config['follower']['port']
                BlockWorkflow.http(f'hardware/arms/{port}/observe',{'profile':profile.name})
        while True:
            emit({'type':'hardware_preview','data':BlockWorkflow.http('hardware/arms')})
            sleep(.05)

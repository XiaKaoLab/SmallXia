"""功能：只读订阅已有真机控制反馈，不打开串口、不刷新控制租约。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
from time import sleep
from ..blocks.workflow import BlockWorkflow

class HardwarePreviewStream:
    @staticmethod
    def run(emit):
        while True:
            emit({'type':'hardware_preview','data':BlockWorkflow.http('hardware/arms')})
            sleep(.05)

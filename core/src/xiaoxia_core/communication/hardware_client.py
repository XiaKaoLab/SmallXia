"""供积木显式连接已验证从臂、等待限速动作到位，并在结束时释放控制。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import re
from time import monotonic, sleep

from ..blocks.workflow import BlockWorkflow


class HardwareClient:
    def __init__(self, port):
        if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
            raise ValueError('请选择 COM 口')
        self.endpoint = f'hardware/arms/{port}'

    def connect(self, profile, enable_motion=False):
        result = BlockWorkflow.http(self.endpoint + '/connect', {'profile': profile, 'enable_motion': enable_motion})
        BlockWorkflow.track(self.endpoint + '/stop')
        return self.wait(ready=True)

    def wait(self, ready=False):
        deadline = monotonic() + 120
        while monotonic() < deadline:
            state = BlockWorkflow.http(self.endpoint)
            if state['status'] == 'ready':
                return state
            if state['status'] not in ('connecting', 'moving'):
                raise RuntimeError(state.get('error', '真机控制已停止'))
            sleep(.05)
        self.stop()
        raise TimeoutError('等待真机到位超时')

    def move(self, positions):
        BlockWorkflow.http(self.endpoint + '/motions', {'joint_positions': positions, 'unit': 'rad'})
        return self.wait()

    def stop(self):
        return BlockWorkflow.http(self.endpoint + '/stop', {})

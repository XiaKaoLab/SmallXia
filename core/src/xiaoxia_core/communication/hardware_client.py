"""供积木显式连接已验证从臂、等待限速动作到位，并在结束时释放控制。
Created on 2026-11-02; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
import re
import json
import os
from pathlib import Path
from time import monotonic, sleep

from ..blocks.workflow import BlockWorkflow


class HardwareClient:
    def __init__(self, port):
        if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
            raise ValueError('请选择 COM 口')
        self.port=port
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


    def ensure_connected(self, profile='so100.local.yaml'):
        sessions=BlockWorkflow.http('hardware/arms')['sessions']
        current=next((s for s in sessions if s['port']==self.port and s['status'] in ('connecting','ready','moving')),None)
        if current:
            if current.get('profile')!=profile:raise ValueError('机械臂配置不匹配')
            BlockWorkflow.track(self.endpoint+'/stop')
            return self.wait(ready=True)
        check=BlockWorkflow.http('sim2real/checks',{'port':self.port,'profile':profile})
        if not check.get('mapping_verified') or check.get('missing_mapping_joints'):
            raise ValueError('请先完成关节映射')
        if not check['ready_for_connection']:
            raise ValueError('；'.join(check['blockers']))
        return self.connect(profile,enable_motion=True)

    def move_connected(self, positions):
        self.ensure_connected()
        return self.move(positions)

    def interactive(self, positions):
        """单独运行位置积木时保持控制，滑条只更新该已有会话。"""
        self.ensure_connected()
        try:
            BlockWorkflow.http(self.endpoint+'/motions',{'joint_positions':positions,'unit':'rad'})
            while True:
                directory=os.environ.get('XIAOXIA_PROGRAM_DIR')
                if directory and (Path(directory)/'stop').exists():break
                state=BlockWorkflow.http(self.endpoint)
                if state['status'] not in ('ready','moving'):
                    raise RuntimeError(state.get('error') or '真机控制已停止')
                print(json.dumps({'hardware_feedback':{**state,'target':f'serial:{self.port}',
                    'source':'hardware_feedback','type':'hardware_feedback'}},ensure_ascii=False),flush=True)
                sleep(.4)
        finally:self.stop()

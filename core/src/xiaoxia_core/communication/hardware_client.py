"""供积木显式连接已验证从臂、等待限速动作到位，并在结束时释放控制。
Created on 2026-11-02; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""
import re
import json
import os
from pathlib import Path
from time import monotonic, sleep

from ..blocks.workflow import BlockWorkflow


class HardwareClient:
    _heartbeats = {}
    def __init__(self, port):
        if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
            raise ValueError('请选择 COM 口')
        self.port=port
        self.endpoint = f'hardware/arms/{port}'

    def connect(self, profile, enable_motion=False):
        result = BlockWorkflow.http(self.endpoint + '/connect', {'profile': profile, 'enable_motion': enable_motion})
        BlockWorkflow.track(self.endpoint + '/stop')
        return self.wait(ready=True)

    def wait(self, ready=False, motion_id=None):
        from .motion_progress import MotionProgress
        progress = MotionProgress()
        while True:
            state = BlockWorkflow.http(self.endpoint)
            if motion_id is not None and state.get('motion_id') != motion_id:
                raise RuntimeError('目标已被其他动作替换')
            if state['status'] == 'ready' and (motion_id is None or state.get('reached_motion_id') == motion_id):
                return state
            if state['status'] not in ('connecting', 'moving'):
                raise RuntimeError(state.get('error', '真机控制已停止'))
            if state.get('target') and state.get('joint_positions'):
                try: progress.update(state['joint_positions'], state['target'])
                except RuntimeError:
                    self.stop()
                    raise
            sleep(.05)

    def move(self, positions, frame='control'):
        receipt = BlockWorkflow.http(self.endpoint + '/motions', {'joint_positions': positions, 'unit': 'rad', 'frame': frame})
        return self.wait(motion_id=receipt['motion_id'])

    def stop(self):
        return BlockWorkflow.http(self.endpoint + '/stop', {})

    def enable(self, profile='so100.local.yaml'):
        state = self.ensure_connected(profile)
        heartbeat = self._heartbeats.pop(self.port, None)
        if heartbeat: heartbeat.close()
        from .control_heartbeat import ControlHeartbeat
        self._heartbeats[self.port] = ControlHeartbeat(self.port).start()
        return state

    def disable(self):
        from .motion_progress import MotionProgress
        progress = MotionProgress('回位没有进展，请检查实际关节状态')
        heartbeat = self._heartbeats.pop(self.port, None)
        if heartbeat: heartbeat.close()
        state = BlockWorkflow.http(self.endpoint + '/disable', {})
        while state['status'] in ('connecting', 'ready', 'moving', 'returning_zero'):
            if state['status'] == 'returning_zero' and state.get('start_joint_positions'):
                progress.update(state['joint_positions'], state['start_joint_positions'])
            sleep(.05)
            state = BlockWorkflow.http(self.endpoint)
        if state['status'] != 'stopped' or not state.get('release', {}).get('torque_disabled'):
            raise RuntimeError(state.get('error') or '未确认失能完成')
        return state


    def ensure_connected(self, profile='so100.local.yaml'):
        sessions=BlockWorkflow.http('hardware/arms')['sessions']
        current=next((s for s in sessions if s['port']==self.port and s['status'] in ('connecting','ready','moving')),None)
        if current:
            if current.get('profile')!=profile:raise ValueError('机械臂配置不匹配')
            BlockWorkflow.track(self.endpoint+'/stop')
            return self.wait(ready=True)
        check=BlockWorkflow.http('sim2real/checks',{'port':self.port,'profile':profile})
        if check.get('coordinate_basis')!='official_calibration' and (not check.get('mapping_verified') or check.get('missing_mapping_joints')):
            raise ValueError('请先完成关节映射')
        if not check['ready_for_connection']:
            raise ValueError('；'.join(check['blockers']))
        return self.connect(profile,enable_motion=True)

    def move_connected(self, positions, frame='control'):
        self.ensure_connected()
        return self.move(positions, frame=frame)

    def interactive(self, positions, frame='control'):
        """运行指定坐标系的绝对位置并保持控制；编辑滑条只作仿真预览。"""
        try:self.ensure_connected()
        except ValueError as error:
            if str(error)!='请先完成关节映射':raise
            calibration=BlockWorkflow.http('sim2real/calibrations',{'port':self.port,'profile':'so100.local.yaml','resume_control':True})
            print(json.dumps({'coordinate_calibration':calibration},ensure_ascii=False),flush=True)
            state=calibration
            try:
                while True:
                    directory=os.environ.get('XIAOXIA_PROGRAM_DIR')
                    if directory and (Path(directory)/'stop').exists():return
                    state=BlockWorkflow.http('sim2real/calibrations/'+calibration['id'])
                    if state['stage']=='saved':break
                    if state['stage']=='cancelled':return
                    sleep(.4)
            finally:
                if state.get('stage')!='saved':
                    BlockWorkflow.http('sim2real/calibrations/'+calibration['id']+'/cancel',{})
            self.ensure_connected()
        try:
            BlockWorkflow.http(self.endpoint+'/motions',{'joint_positions':positions,'unit':'rad','frame':frame})
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

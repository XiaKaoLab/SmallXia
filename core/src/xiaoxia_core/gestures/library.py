"""功能：查询本地动作、相对当前姿态缩放，并复用后台程序编排仿真或真机。
Created on 2026-11-08; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""
import json
import math
import os
from pathlib import Path
from time import monotonic, sleep
from ..blocks.workflow import BlockWorkflow
from ..safety import JOINTS


class GestureLibrary:
    root = Path(__file__).resolve().parents[3] / 'data/gesture_library'

    def catalog(self):
        path = self.root / 'catalog.json'
        if not path.exists(): raise ValueError('动作库未安装，请运行 core/scripts/import_gesture_commands.py')
        return json.loads(path.read_text(encoding='utf8'))

    def episode(self, name, variant=0):
        item = next((a for a in self.catalog()['actions'] if name in (a['id'], a['name'])), None)
        if item is None: raise ValueError('未知动作，请先查询动作库')
        episodes = json.loads((self.root / (item['id']+'.json')).read_text(encoding='utf8'))['episodes']
        if not isinstance(variant, int) or not 0 <= variant < len(episodes): raise ValueError('动作示例编号无效')
        return episodes[variant]

    def plan(self, actions, amplitude_deg, variant=0):
        if not isinstance(actions, list) or not actions or any(not isinstance(a, str) for a in actions): raise ValueError('请提供动作名称列表')
        if not isinstance(amplitude_deg, (float, int)) or isinstance(amplitude_deg, bool) or not math.isfinite(amplitude_deg) or amplitude_deg <= 0: raise ValueError('动作幅度必须为有限正数')
        return [self.episode(name, variant) for name in actions]

    @staticmethod
    def stopped():
        directory = os.environ.get('XIAOXIA_PROGRAM_DIR')
        return bool(directory and (Path(directory)/'stop').exists())

    def play(self, actions, target='simulation', amplitude_deg=15, variant=0, profile='so100.local.yaml'):
        episodes = self.plan(actions, amplitude_deg, variant)
        hardware = None
        print(json.dumps({'robot_view': {'target': target}}), flush=True)
        try:
            if target != 'simulation':
                from ..communication.hardware_client import HardwareClient
                hardware = HardwareClient(target.removeprefix('serial:'))
                if Path(profile).name != profile or not profile.endswith('.yaml'): raise ValueError('机械臂配置无效')
                state = hardware.enable(profile)
                anchor = state['render_joint_positions']
                from ..imitation.workflows import HardwareWorkflow
                from ..communication.display_frame import DisplayFrame
                arm = HardwareWorkflow(Path(__file__).resolve().parents[3]/'configs'/profile).arm('follower')
                arm._render_wrist_offset = DisplayFrame.load(arm.port, arm.calibration.raw_calibration)
                validate = lambda pose: arm.control_positions(pose, state['joint_positions'])
            else:
                from ..mcp.server import TableModelTools
                model = TableModelTools(); anchor = model.table_get_state()['joint_positions']
                validate = model.limits.validate
            amplitude = math.radians(amplitude_deg)
            scales = dict.fromkeys(JOINTS, amplitude)
            if hardware:
                # 实测起点可能在校准边界外几个刻度；目标取最近可达点，动作朝可用行程展开。
                control_anchor = {n: max(arm.limits.joints[n].lower, min(arm.limits.joints[n].upper, state['joint_positions'][n])) for n in JOINTS}
                anchor = arm.render_positions(control_anchor)
                for index, name in enumerate(JOINTS):
                    values = [f['pose'][index] for e in episodes for f in e['frames']]
                    bounds = arm.limits.joints[name]
                    positive_room = bounds.upper-control_anchor[name]
                    negative_room = control_anchor[name]-bounds.lower
                    candidates = []
                    for direction in (1, -1):
                        positive = max(0, max(values)*direction, min(values)*direction)
                        negative = max(0, -max(values)*direction, -min(values)*direction)
                        size = min(amplitude, positive_room/positive if positive else amplitude, negative_room/negative if negative else amplitude)
                        candidates.append((size, direction))
                    size, direction = max(candidates, key=lambda item: item[0])
                    scales[name] = max(0, size-1e-7)*direction
                print(json.dumps({'gesture_retarget': {'source': 'measured_hardware_pose', 'axis_amplitude_deg': {n: math.degrees(s) for n,s in scales.items()}, 'note': '负幅度表示朝可用行程反向摆动，幅度不足的轴缩小'}}, ensure_ascii=False), flush=True)
            # 全序列预检；越界时明确报错，不静默裁剪或改变动作语义。
            for episode in episodes:
                frames = [*episode['frames'], {'t': episode['duration']+.75, 'pose': [0.0]*6}]
                for frame in frames:
                    validate({n: anchor[n]+scales[n]*v for n,v in zip(JOINTS, frame['pose'])})
            for name, episode in zip(actions, episodes):
                print(json.dumps({'gesture': {'name': name, 'target': target, 'physical': hardware is not None, 'source_episode': episode['episode'], 'representation': 'relative_shape_normalized'}}), flush=True)
                previous = {'t': 0, 'pose': [0.0]*6}
                frames = [*episode['frames'], {'t': episode['duration']+.75, 'pose': [0.0]*6}]
                for frame in frames:
                    if self.stopped(): return
                    pose = {n: anchor[n]+scales[n]*v for n,v in zip(JOINTS, frame['pose'])}
                    if hardware:
                        # 示教动作连续衔接，不在每个小关键帧等待严格位置误差或触发停滞判定。
                        measured = BlockWorkflow.http(hardware.endpoint)
                        receipt = BlockWorkflow.http(hardware.endpoint+'/motions', {'joint_positions': pose, 'unit': 'rad', 'frame': 'so100_mid_calib'})
                        accepted = receipt.get('target', measured['joint_positions'])
                        travel = max(abs(accepted[n]-measured['joint_positions'][n]) for n in JOINTS)
                        duration = max(frame['t']-previous['t'], travel/max(measured.get('max_velocity', .15), .001)+.15)
                        deadline = monotonic()+duration
                        while monotonic()<deadline:
                            if self.stopped(): return
                            observed = BlockWorkflow.http(hardware.endpoint)
                            if observed['status'] not in ('ready', 'moving'):
                                raise RuntimeError(observed.get('error') or '真机控制已停止')
                            sleep(.05)
                    else:
                        duration = max(0, frame['t']-previous['t']); began = monotonic()
                        while True:
                            if self.stopped(): return
                            fraction = min(1, (monotonic()-began)/duration) if duration else 1
                            values = {n: anchor[n]+amplitude*(a+(b-a)*fraction) for n,a,b in zip(JOINTS, previous['pose'], frame['pose'])}
                            model.table_move_joints(**values)
                            if fraction >= 1: break
                            sleep(.05)
                    previous = frame
        finally:
            if hardware: hardware.disable()

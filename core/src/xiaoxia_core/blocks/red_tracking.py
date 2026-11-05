"""功能：红色物体视觉跟随积木及 Python API，支持目标平滑、丢失保持和单窗口预览。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
import json
import re
from math import exp, isfinite
from pathlib import Path
from threading import Event
from time import monotonic, sleep, time, time_ns
from uuid import uuid4

from .workflow import BlockWorkflow
from ..collection.frame_client import CameraFrameClient
from ..collection.red_object import RedObjectDetector
from ..communication.control_heartbeat import ControlHeartbeat
from ..imitation.api_jobs import atomic_json, identifier


class RedTrackingPreview:
    root = Path(__file__).resolve().parents[3] / 'data/red_tracking'

    @classmethod
    def stream(cls, identity, emit):
        path = cls.root / (identifier(identity) + '.json')
        previous = None
        while True:
            state = json.loads(path.read_text(encoding='utf-8'))
            if state['revision'] != previous:
                emit({'type': 'red_tracking', 'data': state})
                previous = state['revision']
            if state['status'] in ('stopped', 'failed') or time_ns() - state['updated_at_ns'] > 10_000_000_000:
                emit({'type': 'completed'})
                return
            sleep(.08)


class RedObjectTracker:
    def __init__(self):
        self.detector = RedObjectDetector()
        self.center = None
        self.preview = {}

    def publish(self, **values):
        self.preview.update(values, revision=self.preview.get('revision', 0)+1, updated_at_ns=time_ns())
        RedTrackingPreview.root.mkdir(parents=True, exist_ok=True)
        atomic_json(RedTrackingPreview.root / (self.preview['id']+'.json'), self.preview)

    def run(self, target='simulation', camera='virtual', seconds=0, *, horizontal=1, vertical=-1, stop_event=None):
        if target != 'simulation' and not re.fullmatch(r'serial:COM[1-9][0-9]*', target):
            raise ValueError('请选择仿真或 COM 串口')
        physical = target != 'simulation'
        if physical and camera != 'real' and not re.fullmatch(r'opencv_[0-9a-f]{16}', camera):
            raise ValueError('真机跟随需要真实相机')
        if horizontal not in (-1, 1) or vertical not in (-1, 1): raise ValueError('跟随方向无效')
        if isinstance(seconds, bool) or not isinstance(seconds, (int,float)) or not isfinite(seconds) or seconds < 0:
            raise ValueError('跟随时长不能为负数，0 表示持续运行')
        stop = stop_event or Event()
        endpoint = f'hardware/arms/{target[7:]}' if physical else 'robots/table'
        heartbeat = None
        self.preview = {'id':uuid4().hex, 'target':target, 'source':camera, 'physical':physical, 'status':'tracking', 'found':False}
        held = False
        last_sequence = None
        started = previous = monotonic()

        def state():
            value = BlockWorkflow.http(endpoint if physical else endpoint+'/state')
            if physical and (value['status'] not in ('ready','moving') or value.get('feedback_age_ms') is None or value['feedback_age_ms'] > 500):
                raise RuntimeError(value.get('error') or '请先使能机械臂')
            return value

        def move(positions):
            body = {'joint_positions':positions, 'unit':'rad'}
            if physical: body['max_velocity'] = .12
            else: body.update(request_id=str(uuid4()), expires_at_ms=int(time()*1000)+900)
            return BlockWorkflow.http(endpoint+'/motions', body)

        try:
            state()
            if physical:
                limits = BlockWorkflow.http(endpoint+'/limits')['limits']
                heartbeat = ControlHeartbeat(target[7:]).start()
                BlockWorkflow.track(endpoint+'/stop')
            else:
                from ..mcp.server import TableModelTools
                limits = TableModelTools().table_get_limits()
            self.publish()
            print(json.dumps({'red_tracking': {'id':self.preview['id'], 'source':camera, 'physical':physical}},ensure_ascii=False),flush=True)
            while not stop.is_set() and (seconds == 0 or monotonic()-started < seconds):
                tick = monotonic()
                frame = CameraFrameClient().read(camera)
                if physical and frame.get('physical') is not True: raise ValueError('相机来源不是实拍')
                if frame.get('sequence') == last_sequence and frame.get('age_ms',0) < 800:
                    stop.wait(max(0, .2-(monotonic()-tick)))
                    continue
                fresh = frame.get('sequence') != last_sequence and frame.get('age_ms',0) < 800
                detection = self.detector.detect(frame) if fresh else {'found':False,'box':None}
                last_sequence = frame.get('sequence')
                current = state()['joint_positions']
                dt = min(.3, max(.02, monotonic()-previous)); previous = monotonic()
                centered = False
                if detection['found']:
                    point = (detection['normalized_x'], detection['normalized_y'])
                    alpha = 1-exp(-dt/.18)
                    self.center = point if self.center is None else tuple(a+alpha*(b-a) for a,b in zip(self.center,point))
                    errors = [value-.5 for value in self.center]
                    deltas = [0 if abs(value) < .04 else max(-.12,min(.12,value*.6))*dt for value in errors]
                    centered = not any(deltas)
                    positions = dict(current)
                    for name, delta, sign in zip(('shoulder_pan','wrist_flex'),deltas,(horizontal,vertical)):
                        positions[name] = max(limits[name]['lower'],min(limits[name]['upper'],current[name]+sign*delta))
                    if not centered: move(positions)
                    elif not held: move(current)
                    held = centered
                else:
                    self.center = None
                    if not held: move(current)
                    held = True
                self.publish(status='centered' if centered else 'tracking' if detection['found'] else 'searching',
                             **detection, width=frame['width'], height=frame['height'],
                             image=('data:image/jpeg;base64,'+frame['image_base64']) if physical else None)
                stop.wait(max(0, .2-(monotonic()-tick)))
            return {'id':self.preview['id'], 'physical':physical, 'target':target}
        except BaseException:
            if physical:
                try: BlockWorkflow.http(endpoint+'/disable', {})
                except Exception: pass
            self.publish(status='failed')
            raise
        finally:
            try:
                if self.preview.get('status') != 'failed':
                    try: move(state()['joint_positions'])
                    finally: self.publish(status='stopped')
            finally:
                if heartbeat: heartbeat.close()

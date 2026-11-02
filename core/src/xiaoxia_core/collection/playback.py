"""原始编码器录制的仿真相对回放，按采样时间播放并提供暂停、继续和停止。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from copy import deepcopy
import hashlib
import json
from math import isfinite, pi
from pathlib import Path
import re
from threading import Condition, RLock, Thread
from time import monotonic, time_ns
from uuid import uuid4

from ..imitation.api_jobs import atomic_json, identifier
from ..safety import JOINTS


class RecordingPlaybackAPI:
    prefix = '/api/v1/collection'

    def __init__(self, recordings: Path, root: Path, limits, read_pose, apply_pose):
        self.recordings, self.root, self.limits = recordings, root, limits
        self.read_pose, self.apply_pose = read_pose, apply_pose
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.sessions = {}
        for path in self.root.glob('*/status.json'):
            state = json.loads(path.read_text(encoding='utf-8'))
            if state['status'] in ('running', 'paused'):
                state.update(status='interrupted', error='服务重启，未自动恢复播放')
                atomic_json(path, state)

    def recording(self, recording_id):
        if not isinstance(recording_id, str) or not re.fullmatch(r'hardware(?:-motion)?-\d{8}-\d{6}-[0-9a-f]{8}', recording_id):
            raise ValueError('请选择已保存的原始机械臂录制 ID')
        directory = self.recordings / recording_id
        state = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        if state.get('status') != 'succeeded' or state.get('format') != 'xiaoxia_raw_encoder_v1':
            raise ValueError('录制未成功完成或格式不受支持')
        return directory, state

    def catalog(self):
        recordings = []
        for path in self.recordings.glob('*/manifest.json'):
            try:
                _, state = self.recording(path.parent.name)
                recordings.append({'id': path.parent.name, 'frames': state['frames'], 'port': state['port'],
                    'duration_s': state.get('duration_wall_s'), 'motion': bool(state.get('moving_joints')),
                    'playback_target': 'table', 'mapping': 'relative_display_only'})
            except (ValueError, OSError, KeyError):
                continue
        return {'recordings': sorted(recordings, key=lambda item: item['id'], reverse=True)}

    def start(self, body):
        with self.lock:
            if any(session.state['status'] in ('running', 'paused') for session in self.sessions.values()):
                raise ValueError('已有录制正在播放，请先停止')
            speed = body.get('speed', 1)
            if type(speed) not in (int, float) or not isfinite(speed) or not .1 <= speed <= 4:
                raise ValueError('播放速度需要 0.1–4 倍')
            recording_id = body.get('recording_id', 'latest_motion')
            if recording_id == 'latest_motion':
                candidates = [item for item in self.catalog()['recordings'] if item['motion']]
                if not candidates: raise ValueError('没有可播放的运动录制')
                recording_id = candidates[0]['id']
            directory, manifest = self.recording(recording_id)
            raw = (directory / 'frames.jsonl').read_bytes()
            digest = manifest.get('files', {}).get('frames.jsonl')
            if digest and hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('录制文件校验失败')
            rows = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
            if not 2 <= len(rows) <= 216001 or len(rows) != manifest['frames']:
                raise ValueError('录制帧数无效')
            previous = None
            for row in rows:
                ticks, timestamp = row['position_ticks'], row['monotonic_ns']
                if set(ticks) != set(JOINTS) or any(type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 4095 for value in ticks.values()):
                    raise ValueError('录制编码器帧无效')
                if type(timestamp) is not int or (previous is not None and timestamp <= previous):
                    raise ValueError('录制时间戳必须严格递增')
                previous = timestamp
            duration = (rows[-1]['monotonic_ns'] - rows[0]['monotonic_ns']) / 1e9
            if not 0 < duration <= 3601:
                raise ValueError('录制时间范围无效')
            reference = body.get('reference', self.read_pose())
            self.limits.validate(reference)
            directions = body.get('directions', {name: 1 for name in JOINTS})
            if set(directions) != set(JOINTS) or any(type(value) is not int or value not in (-1, 1) for value in directions.values()):
                raise ValueError('需要六轴正反方向 ±1')
            poses, angles, last = [], dict(reference), rows[0]['position_ticks']
            for row in rows:
                ticks = row['position_ticks']
                for name in JOINTS:
                    delta = ((ticks[name] - last[name] + 2047.5) % 4095) - 2047.5
                    angles[name] += directions[name] * delta * 2 * pi / 4095
                poses.append(dict(angles))
                last = ticks
            identity = uuid4().hex
            session = PlaybackSession(self, identity, rows, poses, {'id': identity, 'recording_id': directory.name,
                'status': 'running', 'physical': False, 'target': 'table', 'mapping': 'relative_display_only',
                'speed': speed, 'frame_index': 0, 'frames': len(rows), 'progress': 0,
                'duration_s': duration, 'reference': reference, 'directions': directions,
                'joint_positions': reference, 'limited': False, 'created_at_ns': time_ns()})
            self.sessions[identity] = session
            session.save()
            Thread(target=session.run, daemon=True).start()
            return self.get(identity)

    def get(self, playback_id):
        identity = identifier(playback_id)
        if identity in self.sessions:
            session = self.sessions[identity]
            with session.condition:
                return deepcopy(session.state)
        return json.loads((self.root / identity / 'status.json').read_text(encoding='utf-8'))

    def control(self, playback_id, operation):
        identity = identifier(playback_id)
        session = self.sessions.get(identity)
        if session is None:
            raise ValueError('此播放进程不存在，请查询状态或重新开始')
        with session.condition:
            if session.state['status'] in ('running', 'paused'):
                if operation == 'pause': session.state['status'] = 'paused'
                elif operation == 'resume': session.state['status'] = 'running'
                elif operation == 'stop': session.state['status'] = 'stopped'
                else: raise ValueError('未知播放控制')
                session.save()
                session.condition.notify_all()
            return deepcopy(session.state)

    def handle(self, method, path, body):
        parts = path.removeprefix(self.prefix).strip('/').split('/')
        try:
            if method == 'GET' and parts == ['recordings']: return 200, self.catalog()
            if method == 'POST' and parts == ['playbacks']: return 202, self.start(body or {})
            if method == 'GET' and len(parts) == 2 and parts[0] == 'playbacks': return 200, self.get(parts[1])
            if method == 'POST' and len(parts) == 3 and parts[0] == 'playbacks' and parts[2] in ('pause', 'resume', 'stop'):
                return 200, self.control(parts[1], parts[2])
            return 404, {'error': 'route_not_found'}
        except FileNotFoundError: return 404, {'error': 'resource_not_found'}
        except (ValueError, TypeError, KeyError) as error: return 422, {'error': str(error)}

    def snapshot(self):
        with self.lock:
            if not self.sessions:
                return None
            session = next(reversed(self.sessions.values()))
            with session.condition:
                return {key: session.state[key] for key in ('id', 'status', 'frame_index', 'progress')}

    def close(self):
        for identity in list(self.sessions):
            self.control(identity, 'stop')


class PlaybackSession:
    def __init__(self, api, identity, rows, poses, state):
        self.api, self.rows, self.poses, self.state = api, rows, poses, state
        self.directory = api.root / identity
        self.directory.mkdir()
        self.condition = Condition()

    def save(self):
        atomic_json(self.directory / 'status.json', self.state)

    def wait(self, seconds):
        remaining = seconds
        while True:
            if self.state['status'] == 'stopped': return False
            if self.state['status'] == 'paused':
                self.condition.wait()
                continue
            if remaining <= 0: return True
            started = monotonic()
            self.condition.wait(timeout=min(.02, remaining))
            remaining -= monotonic() - started

    def run(self):
        try:
            previous_started = monotonic()
            for index, (row, desired) in enumerate(zip(self.rows, self.poses)):
                with self.condition:
                    delay = 0 if not index else (row['monotonic_ns'] - self.rows[index - 1]['monotonic_ns']) / 1e9 / self.state['speed'] - (monotonic() - previous_started)
                    if not self.wait(delay): break
                    previous_started = monotonic()
                    constrained = {name: max(self.api.limits.joints[name].lower, min(self.api.limits.joints[name].upper, value)) for name, value in desired.items()}
                    receipt = self.api.apply_pose(constrained)
                    self.state.update(frame_index=index, progress=(index + 1) / len(self.rows),
                        joint_positions=receipt['applied_joint_positions'],
                        requested_joint_positions=desired,
                        limited=bool(receipt.get('limited')) or constrained != desired,
                        outside_device_calibration=row.get('outside_device_calibration', []))
                    self.save()
            with self.condition:
                if self.state['status'] != 'stopped': self.state['status'] = 'completed'
                self.save()
        except Exception as error:
            with self.condition:
                self.state.update(status='failed', error=str(error))
                self.save()
        finally:
            self.rows = []
            self.poses = []

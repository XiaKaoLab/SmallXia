"""为 table 模型执行有界 RL 动作，记录实际裁剪动作及前后相机观测。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import base64
from math import isfinite
from threading import Lock
from time import monotonic, sleep, time, time_ns
from uuid import uuid4

from ..contracts import Action
from ..safety import JOINTS


class TableRLEnvironment:
    def __init__(self, limits, frames, routes, authorization):
        self.limits, self.frames, self.routes, self.authorization = limits, frames, routes, authorization
        self._step_lock = Lock()
        self._last_step_at = 0.0

    def observation(self, store, *, after_ns=0):
        _, state = self.routes.handle('GET', '/api/v1/robots/table/state', self.authorization)
        images, metadata = {}, {}
        for camera in store.config['cameras']:
            deadline = monotonic() + 2
            while True:
                frame = self.frames.read(camera)
                if frame['timestamp_ns'] > after_ns:
                    break
                if monotonic() >= deadline:
                    raise ValueError('动作后未收到新的相机帧')
                sleep(0.05)
            name = f'{time_ns()}-{camera}.jpg'
            directory = store.directory / 'images'
            directory.mkdir(exist_ok=True)
            (directory / name).write_bytes(base64.b64decode(frame['image_base64']))
            images[camera] = str(directory / name)
            metadata[camera] = {key: value for key, value in frame.items() if key != 'image_base64'}
        return {'timestamp_ns': time_ns(), 'state': state['joint_positions'], 'images': images,
                'camera_metadata': metadata, 'state_source': 'table_display_target', 'physical': False}

    def step(self, store, body):
        with self._step_lock:
            control = store.control()
            if control['status'] != 'ready':
                raise ValueError('当前 episode 已结束或停止，请先 reset')
            action = body.get('action')
            if not isinstance(action, list) or len(action) != 6 or any(type(v) not in (int, float) or not isfinite(v) or abs(v) > 1 for v in action):
                raise ValueError('action 必须是六维 [-1,1] 归一化关节增量')
            kind = body.get('kind', 'online')
            if kind not in ('online', 'demonstration'):
                raise ValueError('kind 需要 online 或 demonstration')
            sleep(max(0, 1 / store.config['fps'] - (monotonic() - self._last_step_at)))
            before = self.observation(store)
            scale = store.config['max_joint_step_rad']
            current = before['state']
            control = store.control()
            if control['status'] != 'ready':
                raise ValueError('episode 已停止，未发送新动作')
            intervention = control['intervention']
            if intervention:
                target = control['intervention_target'] if control['intervention_expires_ns'] > time_ns() else None
                target = target or current  # 接管超时后保持，不自动交回策略。
            else:
                target = {joint: max(self.limits.joints[joint].lower, min(self.limits.joints[joint].upper,
                          current[joint] + action[index] * scale)) for index, joint in enumerate(JOINTS)}
            target = {joint: current[joint] + max(-scale, min(scale, target[joint] - current[joint])) for joint in JOINTS}
            safe = self.limits.constrain(Action(target), current, 1 / store.config['fps'], 0.25)
            status, receipt = self.routes.handle('POST', '/api/v1/robots/table/motions', self.authorization,
                {'request_id': str(uuid4()), 'expires_at_ms': int(time() * 1000) + 900,
                 'unit': 'rad', 'joint_positions': safe.joint_positions})
            if status not in (200, 202):
                raise ValueError(f'模型动作未确认：{receipt}')
            self._last_step_at = monotonic()
            dispatched = time_ns()
            after = self.observation(store, after_ns=dispatched)
            applied = receipt.get('applied_joint_positions', safe.joint_positions)
            if any(abs(after['state'][joint] - applied[joint]) > 1e-6 for joint in JOINTS):
                raise ValueError('动作已发送，但模型状态被其他控制修改；该样本未记录，请读取状态后再操作')
            steps = control['episode_steps'] + 1
            truncated = steps >= store.config['max_episode_steps']
            actual = [(after['state'][joint] - current[joint]) / scale for joint in JOINTS]
            row = {'episode': control['episode'], 'kind': kind, 'observation': before, 'next_observation': after,
                   'action': actual, 'requested_action': action, 'reward': 0.0, 'reward_source': 'pending_human',
                   'terminated': False, 'truncated': truncated, 'intervention': intervention, 'receipt': receipt}
            row_id = store.append(row)
            store.update_control(episode_steps=steps, status='ended' if truncated else 'ready', last_transition_id=row_id)
            return {'transition_id': row_id, 'observation': after, 'reward': 0, 'truncated': truncated,
                    'intervention': intervention, 'receipt': receipt, 'physical': False}

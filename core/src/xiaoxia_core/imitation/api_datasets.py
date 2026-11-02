"""记录模型观测、显式示教目标及统一相机帧，保存可导出 LeRobot 的 episode。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import base64
import json
import re
from pathlib import Path
from threading import RLock
from time import time_ns
from uuid import uuid4

from .api_jobs import atomic_json, identifier


class APIDemonstrations:
    def __init__(self, root, limits, frames, model_state):
        self.root, self.limits, self.frames, self.model_state = root, limits, frames, model_state
        self._lock = RLock()
        root.mkdir(parents=True, exist_ok=True)

    def create(self, body):
        fps = body.get('fps', 2)
        sources = body.get('cameras', [])
        task = body.get('task')
        semantics = body.get('action_semantics', 'explicit_demonstrator_target')
        if semantics not in ('explicit_demonstrator_target', 'waypoint_next_target'):
            raise ValueError('不支持此示教动作标签')
        if type(fps) is not int or not 1 <= fps <= 60:
            raise ValueError('fps 必须是 1–60 的整数')
        if not isinstance(sources, list) or len(sources) > 2 or any(not isinstance(source, str) or (source not in ('virtual', 'real') and not re.fullmatch(r'opencv_[0-9a-f]{16}', source)) for source in sources) or len(set(sources)) != len(sources):
            raise ValueError('cameras 仅支持 virtual、real，不能重复')
        if 'virtual' in sources and fps > 2:
            raise ValueError('当前虚拟画面最多 2 FPS，请降低数据集 fps')
        if not isinstance(task, str) or not task.strip() or len(task) > 500:
            raise ValueError('task 需要 1–500 字的任务描述')
        dataset_id = uuid4().hex
        directory = self.root / dataset_id
        directory.mkdir()
        state_source = body.get('state_source', 'table_display_target')
        if state_source not in ('table_display_target', 'manual_encoder'):
            raise ValueError('不支持此示教来源')
        manifest = {'id': dataset_id, 'status': 'recording', 'fps': fps, 'task': task,
                    'cameras': sources, 'episodes': 0, 'episode_frames': 0, 'total_frames': 0,
                    'unit': 'rad', 'state_source': state_source, 'physical': state_source == 'manual_encoder',
                    'simulated': state_source != 'manual_encoder', 'camera_joint_synchronized': False, 'created_at_ns': time_ns(),
                    'action_semantics': semantics, 'model_frame': 'so100_mid_calib'}
        atomic_json(directory / 'manifest.json', manifest)
        return manifest

    def get(self, dataset_id):
        with self._lock:
            directory = self.root / identifier(dataset_id)
            return json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))

    def append(self, dataset_id, body):
        with self._lock:
            manifest = self.get(dataset_id)
            if manifest['status'] != 'recording':
                raise ValueError('数据集已关闭，不能添加帧')
            action = body.get('action')
            if not isinstance(action, dict) or any(type(v) not in (int, float) for v in action.values()):
                raise ValueError('action 必须显式提供六关节弧度目标；不能把当前状态自动当作动作标签')
            self.limits.validate(action)
            now = time_ns()
            previous = manifest.get('last_sample_ns', 0)
            if now - previous < 1e9 / manifest['fps'] * 0.9:
                raise ValueError('采样间隔小于数据集 fps，请按设定节拍提交')
            if manifest['total_frames'] >= 100000:
                raise ValueError('单数据集最多 100000 帧')
            state = self.model_state()
            if manifest['state_source'] == 'manual_encoder':
                state = body.get('observation')
                self.limits.validate(state)
            directory = self.root / dataset_id
            images, image_metadata, sequences = {}, {}, {}
            fetched = {source: self.frames.read(source) for source in manifest['cameras']}
            for source, frame in fetched.items():
                if manifest.get('last_sequences', {}).get(source) == frame['sequence']:
                    raise ValueError(f'{source} 没有新帧，不能重复记录旧画面')
                if manifest.get('image_shapes', {}).get(source, [frame['height'], frame['width']]) != [frame['height'], frame['width']]:
                    raise ValueError('同一数据集的图像尺寸不能改变')
                relative = f"images/{manifest['total_frames']:08d}-{source}.jpg"
                path = directory / relative
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(base64.b64decode(frame['image_base64']))
                images[source] = relative
                image_metadata[source] = {k: v for k, v in frame.items() if k != 'image_base64'}
                sequences[source] = frame['sequence']
            row = {'timestamp_ns': now, 'observation': state, 'action': action,
                   'images': images, 'camera_metadata': image_metadata}
            with (directory / f"episode-{manifest['episodes']:05d}.jsonl").open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, allow_nan=False) + '\n')
            manifest.update(total_frames=manifest['total_frames'] + 1, episode_frames=manifest['episode_frames'] + 1,
                            last_sample_ns=now, last_sequences=sequences,
                            image_shapes={source: [frame['height'], frame['width']] for source, frame in fetched.items()})
            atomic_json(directory / 'manifest.json', manifest)
            return manifest

    def end_episode(self, dataset_id):
        with self._lock:
            manifest = self.get(dataset_id)
            if manifest['status'] != 'recording' or manifest['episode_frames'] < 2:
                raise ValueError('仅可保存仍在记录且至少有两帧的 episode')
            manifest.update(episodes=manifest['episodes'] + 1, episode_frames=0)
            atomic_json(self.root / dataset_id / 'manifest.json', manifest)
            return manifest

    def finish(self, dataset_id):
        with self._lock:
            manifest = self.get(dataset_id)
            if manifest['status'] == 'recording' and manifest['episode_frames']:
                manifest = self.end_episode(dataset_id)
            if not manifest['episodes'] or manifest['status'] not in ('recording', 'closed'):
                raise ValueError('需要至少一个已保存的 episode')
            manifest['status'] = 'closed'
            atomic_json(self.root / dataset_id / 'manifest.json', manifest)
            return manifest

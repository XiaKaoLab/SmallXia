"""提供独立的物理仿真/只读真机采集会话、命令回执和 v3 数据集结果。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import re
from pathlib import Path
from threading import RLock
from time import time_ns
from uuid import uuid4

from ..imitation.api_jobs import ImitationJobs, atomic_json, identifier
from ..safety import JointLimits
from .capture_queue import CaptureQueue


class CollectionAPI:
    prefix = '/api/v1/collection'

    def __init__(self, root, core, *, frames=None):
        self.root, self.core, self.frames = root, core, frames
        (root / 'sessions').mkdir(parents=True, exist_ok=True)
        self.jobs = ImitationJobs(root / 'jobs', worker_module='xiaoxia_core.collection.capture_worker')
        self._lock = RLock()

    def queue(self, session_id):
        return CaptureQueue(self.root / 'sessions' / identifier(session_id))

    def create(self, source, body):
        task, fps = body.get('task'), body.get('fps', 10)
        if not isinstance(task, str) or not task.strip() or len(task) > 500 or type(fps) is not int or not 1 <= fps <= 60:
            raise ValueError('需要任务描述与 1–60 的整数 fps')
        cameras = body.get('cameras', [])
        if not isinstance(cameras, list) or len(cameras) > 2 or len(set(cameras)) != len(cameras):
            raise ValueError('最多两个不重复的相机 ID')
        for camera in cameras:
            if not isinstance(camera, str) or (source == 'simulation' and camera != 'simulation') or (source == 'hardware' and camera != 'real' and not re.fullmatch('opencv_[0-9a-f]{16}', camera)):
                raise ValueError('仿真相机使用 simulation；真机相机使用已发现的 opencv_ID')
        record_actions = body.get('record_actions', source == 'simulation')
        use_videos = body.get('use_videos', True)
        if type(record_actions) is not bool or type(use_videos) is not bool:
            raise ValueError('record_actions/use_videos 需要布尔值')
        profile = body.get('profile')
        if source == 'hardware':
            if body.get('read_only_confirmed') is not True:
                raise ValueError('真机采集需显式 read_only_confirmed=true；本入口不会控制实机')
            if not isinstance(profile, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+\.local\.yaml', profile):
                raise ValueError('profile 必须为 core/configs 下的 *.local.yaml 文件名')
            from ..imitation.workflows import HardwareWorkflow
            workflow = HardwareWorkflow(self.core / 'configs' / profile)
            # 文件级检查，不连接设备，不自动修正校准。
            workflow.arm('follower')
        timeout = body.get('idle_timeout_s', 600)
        if type(timeout) is not int or not 30 <= timeout <= 3600:
            raise ValueError('idle_timeout_s 需要 30–3600 秒')
        session_id = uuid4().hex
        directory = self.root / 'sessions' / session_id
        directory.mkdir()
        config = {'id': session_id, 'source': source, 'task': task, 'fps': fps, 'cameras': cameras,
                  'record_actions': record_actions, 'use_videos': use_videos, 'profile': profile,
                  'idle_timeout_s': timeout, 'created_at_ns': time_ns(), 'physical': source == 'hardware'}
        atomic_json(directory / 'session.json', config)
        return self.status(session_id)

    def status(self, session_id):
        queue = self.queue(session_id)
        state = queue.state()
        result = {**queue.config, **state}
        if state.get('job_id'):
            result['job'] = self.jobs.get(state['job_id'])
        return result

    def resolve_dataset(self, session_id):
        state = self.status(session_id)
        if state.get('job', {}).get('status') != 'succeeded' or state.get('phase') != 'completed':
            raise ValueError('采集尚未成功结束，不能用于训练')
        if not state['record_actions']:
            raise ValueError('只读观测数据没有动作标签，不能直接用于 ACT 训练')
        return Path(state['job']['result']['dataset']), state['frames']

    def handle(self, method, path, body=None):
        body = body or {}
        parts = path.removeprefix(self.prefix).strip('/').split('/')
        try:
            if method == 'GET':
                if parts == ['sessions']:
                    return 200, {'sessions': [self.status(p.parent.name) for p in (self.root / 'sessions').glob('*/session.json')]}
                if parts == ['jobs']:
                    return 200, {'jobs': self.jobs.list()}
                if len(parts) == 2 and parts[0] == 'jobs':
                    return 200, self.jobs.get(parts[1])
                if len(parts) == 2 and parts[0] == 'sessions':
                    return 200, self.status(parts[1])
                if len(parts) == 4 and parts[0] == 'sessions' and parts[2] == 'commands':
                    return 200, self.queue(parts[1]).command(int(parts[3]))
            if method != 'POST':
                return 404, {'error': 'route_not_found'}
            if parts in (['simulation', 'sessions'], ['hardware', 'sessions']):
                return 201, self.create(parts[0], body)
            if len(parts) == 3 and parts[0] == 'sessions':
                queue = self.queue(parts[1])
                with self._lock:
                    state = queue.state()
                    if parts[2] == 'start':
                        if state.get('job_id'):
                            return 200, self.status(parts[1])
                        job = self.jobs.start('capture', {'session_directory': str(queue.directory)})
                        queue.set(job_id=job['id'])
                        return 202, self.status(parts[1])
                    if parts[2] == 'stop':
                        if state.get('phase') == 'completed':
                            return 200, self.status(parts[1])
                        if state.get('job_id'):
                            self.jobs.stop(state['job_id'])
                        if self.frames is not None and queue.config['source'] == 'hardware':
                            self.frames.close()
                        queue.set(phase='cancelled')
                        return 200, self.status(parts[1])
                    kinds = {'frames': 'capture', 'episodes': 'save_episode', 'finish': 'finish'}
                    if parts[2] in kinds:
                        if not state.get('job_id') or self.jobs.get(state['job_id'])['status'] not in ('queued', 'running'):
                            raise ValueError('请先启动采集；已结束的会话不能追加')
                        if state.get('finish_requested'):
                            raise ValueError('已请求结束采集，请等待回执')
                        if parts[2] == 'frames' and queue.config['record_actions']:
                            action = body.get('action')
                            if not isinstance(action, dict) or any(type(v) not in (int, float) for v in action.values()):
                                raise ValueError('需要显式六关节 action 弧度目标')
                            if queue.config['source'] == 'simulation':
                                limits = JointLimits.from_urdf(self.core / 'assets/so100/so100.urdf')
                            else:
                                from ..imitation.workflows import HardwareWorkflow
                                limits = HardwareWorkflow(self.core / 'configs' / queue.config['profile']).arm('follower').limits
                            limits.validate(action)
                        command = queue.enqueue(kinds[parts[2]], body)
                        if parts[2] == 'finish':
                            queue.set(finish_requested=True)
                        return 202, command
            return 404, {'error': 'route_not_found'}
        except FileNotFoundError:
            return 404, {'error': 'resource_not_found'}
        except (ValueError, TypeError, KeyError) as error:
            return 422, {'error': str(error)}
        except OSError as error:
            return 503, {'error': str(error)}

    def close(self):
        self.jobs.close()

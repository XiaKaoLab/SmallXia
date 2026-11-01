"""将模仿学习 HTTP 路由连接到示教数据、后台 ACT 任务和模型推理。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
from pathlib import Path
from threading import RLock

from .api_datasets import APIDemonstrations
from .api_jobs import ImitationJobs, identifier


class ImitationAPI:
    prefix = '/api/v1/imitation'

    def __init__(self, root: Path, limits, frames, model_state):
        self.datasets = APIDemonstrations(root / 'datasets', limits, frames, model_state)
        self.jobs = ImitationJobs(root / 'jobs')
        self.limits = limits
        self._lock = RLock()

    @staticmethod
    def integer(body, key, default, lower, upper):
        value = body.get(key, default)
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f'{key} 必须是 {lower}–{upper} 的整数')
        return value

    def checkpoint(self, job_id):
        state = self.jobs.get(identifier(job_id))
        if state['kind'] != 'train' or state['status'] != 'succeeded':
            raise ValueError('需要成功完成的训练任务 ID')
        return self.jobs.root / job_id / 'checkpoint'

    def handle(self, method, path, body=None):
        with self._lock:
            return self._handle(method, path, body)

    def _handle(self, method, path, body=None):
        body = body or {}
        parts = path.removeprefix(self.prefix).strip('/').split('/')
        try:
            if method == 'GET':
                if parts == ['datasets']:
                    return 200, {'datasets': [self.dataset_status(p.parent.name) for p in self.datasets.root.glob('*/manifest.json')]}
                if parts == ['jobs']:
                    return 200, {'jobs': self.jobs.list()}
                if len(parts) == 2 and parts[0] == 'jobs':
                    return 200, self.jobs.get(parts[1])
                if len(parts) == 2 and parts[0] == 'datasets':
                    return 200, self.dataset_status(parts[1])
            if method != 'POST':
                return 404, {'error': 'route_not_found'}
            if parts == ['datasets']:
                return 201, self.datasets.create(body)
            if len(parts) == 3 and parts[0] == 'datasets':
                dataset_id = identifier(parts[1])
                if parts[2] == 'frames':
                    return 201, self.datasets.append(dataset_id, body)
                if parts[2] == 'episodes':
                    return 200, self.datasets.end_episode(dataset_id)
                if parts[2] == 'finalize':
                    self.datasets.finish(dataset_id)
                    state = self.dataset_status(dataset_id)
                    if state.get('export_status') == 'succeeded':
                        return 200, state
                    if state.get('export_status') in ('queued', 'running'):
                        return 202, self.jobs.get(state['export_job_id'])
                    return 202, self.jobs.start('export', {'dataset_id': dataset_id,
                        'dataset_directory': str(self.datasets.root / dataset_id)})
            if parts == ['trainings']:
                dataset_id = identifier(body.get('dataset_id'))
                state = self.dataset_status(dataset_id)
                if state.get('export_status') != 'succeeded':
                    raise ValueError('数据集必须先 finalize 并等待导出任务成功')
                device = body.get('device', 'cpu')
                if device not in ('cpu', 'cuda'):
                    raise ValueError('device 仅支持 cpu 或 cuda')
                configuration = {key: self.integer(body, key, default, lower, upper) for key, default, lower, upper in
                                 [('steps', 1000, 1, 1000000), ('batch_size', 4, 1, 128), ('chunk_size', 16, 1, 256)]}
                if state['total_frames'] < configuration['chunk_size']:
                    raise ValueError('数据集帧数少于 chunk_size')
                return 202, self.jobs.start('train', {'dataset_id': dataset_id, 'device': device,
                    'dataset': str(self.jobs.root / state['export_job_id'] / 'dataset'), **configuration})
            if parts in (['predictions'], ['rollouts']):
                checkpoint = self.checkpoint(body.get('training_job_id'))
                device = body.get('device', 'cpu')
                if device not in ('cpu', 'cuda'):
                    raise ValueError('device 仅支持 cpu 或 cuda')
                steps = self.integer(body, 'steps', 1, 1, 1000) if parts == ['rollouts'] else 1
                fps = self.integer(body, 'fps', 2, 1, 30)
                metadata = json.loads((checkpoint / 'imitation.json').read_text(encoding='utf-8'))
                if 'virtual' in metadata['images'] and fps > 2:
                    raise ValueError('虚拟图像策略回放 fps 不得超过 2')
                return 202, self.jobs.start('rollout' if parts == ['rollouts'] else 'predict',
                    {'checkpoint': str(checkpoint), 'device': device, 'steps': steps, 'fps': fps,
                     'target': 'table', 'physical': False})
            if len(parts) == 3 and parts[0] == 'jobs' and parts[2] == 'stop':
                return 200, self.jobs.stop(parts[1])
            return 404, {'error': 'route_not_found'}
        except FileNotFoundError:
            return 404, {'error': 'resource_not_found'}
        except (ValueError, TypeError, KeyError) as error:
            return 422, {'error': str(error)}
        except OSError as error:
            return 503, {'error': str(error)}

    def dataset_status(self, dataset_id):
        state = self.datasets.get(dataset_id)
        exports = []
        for path in self.jobs.root.glob('*/request.json'):
            request = json.loads(path.read_text(encoding='utf-8'))
            if request.get('kind') == 'export' and request.get('dataset_id') == dataset_id:
                exports.append(self.jobs.get(path.parent.name))
        if exports:
            job = max(exports, key=lambda job: job.get('created_at_ns', 0))
            state.update(export_job_id=job['id'], export_status=job['status'])
        return state

    def close(self):
        self.jobs.close()

"""为 Blockly、Agent 或脚本提供模仿学习 API 客户端。
Created on 2026-11-02; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class ImitationClient:
    def request(self, endpoint, body=None):
        request = Request('http://127.0.0.1:8766/api/v1/imitation/' + endpoint,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        try:
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
                from ..blocks.workflow import BlockWorkflow
                BlockWorkflow.track_created('imitation', endpoint, body, result)
                return result
        except HTTPError as error:
            raise RuntimeError(json.loads(error.read()).get('error', str(error))) from None

    def create_dataset(self, task, fps=2, cameras=None, **options):
        return self.request('datasets', {'task': task, 'fps': fps, 'cameras': cameras or [], **options})

    def record_frame(self, dataset_id, action):
        return self.request(f'datasets/{dataset_id}/frames', {'action': action})

    def save_episode(self, dataset_id):
        return self.request(f'datasets/{dataset_id}/episodes', {})

    def finalize(self, dataset_id):
        return self.request(f'datasets/{dataset_id}/finalize', {})

    def dataset(self, dataset_id):
        return self.request(f'datasets/{dataset_id}')

    def train(self, dataset_id, **configuration):
        return self.request('trainings', {'dataset_id': dataset_id, **configuration})

    def predict(self, training_job_id, device='cpu', target='table', camera_sources=None):
        return self.request('predictions', {'training_job_id': training_job_id, 'device': device,
            'target':target,'camera_sources':camera_sources or {}})

    def rollout(self, training_job_id, steps=10, fps=2, device='cpu', target='table', camera_sources=None, camera_source=None):
        return self.request('rollouts', {'training_job_id': training_job_id, 'steps': steps, 'fps': fps, 'device': device,
            'target':target,'camera_sources':camera_sources or {},'camera_source':camera_source})

    def job(self, job_id):
        return self.request(f'jobs/{job_id}')

    def stop(self, job_id):
        return self.request(f'jobs/{job_id}/stop', {})

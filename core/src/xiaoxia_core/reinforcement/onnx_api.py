"""为已有任务提供受限 ONNX 导出、只读动作推理与独立仿真执行入口。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from collections import OrderedDict
import json

from ..imitation.api_jobs import identifier
from ..inference.ball_onnx import BallOnnxPolicy


class BallOnnxAPI:
    def __init__(self, jobs):
        self.jobs = jobs
        self.policies = OrderedDict()

    def source(self, value, *, exported=False):
        if value == 'latest':
            candidates = [job for job in self.jobs.list() if job['status'] == 'succeeded'
                and job['kind'] in (('ball_pickup', 'ball_onnx_export') if exported else ('ball_pickup',))
                and (not exported or (self.jobs.root / job['id'] / 'policy.onnx.json').exists())]
            if not candidates:
                raise ValueError('没有已完成且可用的抓球模型，请先训练或导出 ONNX')
            value = max(candidates, key=lambda job: job.get('created_at_ns', 0))['id']
        job_id = identifier(value)
        job = self.jobs.get(job_id)
        kinds = ('ball_pickup', 'ball_onnx_export') if exported else ('ball_pickup',)
        if job['kind'] not in kinds or job['status'] != 'succeeded':
            raise ValueError('需要已成功完成的抓球训练或对应 ONNX 导出任务')
        directory = self.jobs.root / job_id
        if exported and not (directory / 'policy.onnx.json').exists():
            raise ValueError('模型尚未导出 ONNX，请先执行导出任务')
        return directory

    def export(self, body):
        source = self.source(body.get('training_job_id'))
        for job in self.jobs.list():
            if job['kind'] == 'ball_onnx_export' and job['status'] in ('queued', 'running'):
                request = json.loads((self.jobs.root / job['id'] / 'request.json').read_text(encoding='utf-8'))
                if request['source_directory'] == str(source):
                    raise ValueError('该模型的 ONNX 导出已在运行，请查询现有任务')
        return self.jobs.start('ball_onnx_export', {'source_directory': str(source)}, initial_state={'phase': 'exporting'})

    def predict(self, body):
        source = self.source(body.get('model_job_id'), exported=True)
        key = source.name
        if key not in self.policies:
            self.policies[key] = BallOnnxPolicy(source)
            if len(self.policies) > 4:
                self.policies.popitem(last=False)
        self.policies.move_to_end(key)
        actions = self.policies[key].predict(body.get('states'))
        return {'model_job_id': key, 'actions': actions.tolist(), 'action_space': 'normalized_joint_delta',
                'action_scale_rad': .08, 'deterministic': True, 'runtime': 'onnxruntime',
                'executed': False, 'physical': False}

    def rollout(self, body, rounds, seed):
        source = self.source(body.get('model_job_id'), exported=True)
        from .ball_environment import BallPickupEnvironment
        manifest = json.loads((source / 'policy.onnx.json').read_text(encoding='utf-8'))
        if manifest.get('environment_version') != BallPickupEnvironment.version:
            raise ValueError('模型使用旧抓球环境，请在新版物理与奖励环境重新训练')
        if any(job['kind'] in ('ball_pickup', 'ball_onnx_rollout') and job['status'] in ('queued', 'running') for job in self.jobs.list()):
            raise ValueError('已有抓球训练或 ONNX 推理运行中，请先停止或等待结束')
        return self.jobs.start('ball_onnx_rollout', {'source_directory': str(source), 'rounds': rounds, 'seed': seed},
            initial_state={'task': '拿取小球 · ONNX 推理', 'phase': 'initializing', 'num_envs': 1, 'rounds': rounds,
                           'completed_episodes': 0, 'total_episodes': rounds, 'progress': 0, 'score': None, 'physical': False})

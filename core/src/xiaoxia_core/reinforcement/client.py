"""强化学习 HTTP 客户端，复用本机访问令牌。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class ReinforcementClient:
    def request(self, endpoint, body=None):
        request = Request('http://127.0.0.1:8766/api/v1/reinforcement/' + endpoint,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        try:
            with urlopen(request, timeout=10) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(json.loads(error.read()).get('error', str(error))) from None

    def create_session(self, task, **configuration):
        return self.request('sessions', {'task': task, **configuration})

    def train_ball(self, num_envs=4, rounds=100, device='cpu', seed=42):
        return self.request('ball-trainings', {'num_envs': num_envs, 'rounds': rounds, 'device': device, 'seed': seed})

    def session(self, session_id):
        return self.request(f'sessions/{session_id}')

    def step(self, session_id, action, kind='online'):
        return self.request(f'sessions/{session_id}/step', {'action': action, 'kind': kind})

    def intervene(self, session_id, enabled, joint_positions=None):
        return self.request(f'sessions/{session_id}/intervention', {'enabled': enabled, 'joint_positions': joint_positions})

    def feedback(self, session_id, success, **values):
        return self.request(f'sessions/{session_id}/feedback', {'success': success, **values})

    def label(self, session_id, reward):
        return self.request(f'sessions/{session_id}/labels', {'reward': reward})

    def reset(self, session_id):
        return self.request(f'sessions/{session_id}/reset', {})

    def learner(self, session_id, **configuration):
        return self.request('learners', {'session_id': session_id, **configuration})

    def actor(self, session_id, learner_job_id, **configuration):
        return self.request('actors', {'session_id': session_id, 'learner_job_id': learner_job_id, **configuration})

    def predict(self, session_id, learner_job_id, device='cpu'):
        return self.request('predictions', {'session_id': session_id, 'learner_job_id': learner_job_id, 'device': device})

    def train_reward(self, session_id, **configuration):
        return self.request('reward-trainings', {'session_id': session_id, **configuration})

    def job(self, job_id):
        return self.request(f'jobs/{job_id}')

    def stop_job(self, job_id):
        return self.request(f'jobs/{job_id}/stop', {})

    def stop_session(self, session_id):
        return self.request(f'sessions/{session_id}/stop', {})

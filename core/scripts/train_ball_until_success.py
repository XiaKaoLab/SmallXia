"""持续扩量训练抓球策略，直到独立 ONNX 推理出现真实物理抓取成功。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from pathlib import Path
from time import sleep
from xiaoxia_core.imitation.api_jobs import atomic_json
from xiaoxia_core.reinforcement.client import ReinforcementClient


class PickupTrainingCampaign:
    def __init__(self):
        self.client = ReinforcementClient()
        self.path = Path(__file__).resolve().parents[1] / 'data/runtime/pickup-campaign.json'
        self.report = {'status': 'running', 'acceptance': 'independent_onnx_physical_grasp', 'batches': []}

    def save(self):
        atomic_json(self.path, self.report)

    def wait(self, identity, field):
        while True:
            state = self.client.job(identity)
            self.report[field] = state
            self.save()
            if state['status'] not in ('queued', 'running'):
                if state['status'] != 'succeeded':
                    raise RuntimeError(f"{identity}: {state.get('error', state['status'])}")
                return state
            sleep(3)

    def run(self):
        previous = None
        batch = 0
        try:
            while True:
                batch += 1
                training = self.client.train_ball(num_envs=8, rounds=min(1000 * batch, 10000), device='cuda',
                    seed=42 + batch - 1, warm_start_job_id=previous, demonstration_episodes=min(64 * batch, 256),
                    pretraining_updates=min(5000 * batch, 20000), stop_on_success=True)
                self.report['batch'] = batch
                self.report['training_job_id'] = training['id']
                self.wait(training['id'], 'training')
                evaluation = self.client.rollout_onnx(training['id'], rounds=20, seed=20261103 + batch)
                self.report['evaluation_job_id'] = evaluation['id']
                result = self.wait(evaluation['id'], 'evaluation')
                successes = result.get('successes', 0)
                self.report['batches'].append({'training_job_id': training['id'],
                    'evaluation_job_id': evaluation['id'], 'successes': successes, 'rounds': 20})
                self.save()
                if successes > 0:
                    self.report.update(status='succeeded', successful_model_job_id=training['id'],
                        success_rate=successes / 20, robust_grasp_validated=successes >= 16)
                    self.save()
                    return
                previous = training['id']
        except Exception as error:
            self.report.update(status='failed', error=str(error))
            self.save()
            raise


if __name__ == '__main__':
    PickupTrainingCampaign().run()

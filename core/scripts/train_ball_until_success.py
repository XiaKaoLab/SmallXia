"""持续扩量训练抓球策略，直到独立 ONNX 三组验收全部成功。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from pathlib import Path
from time import sleep
from xiaoxia_core.imitation.api_jobs import atomic_json
from xiaoxia_core.reinforcement.client import ReinforcementClient


class PickupTrainingCampaign:
    def __init__(self, demonstration_job_id=None):
        self.demonstration_job_id = demonstration_job_id
        self.client = ReinforcementClient()
        self.path = Path(__file__).resolve().parents[1] / 'data/runtime/pickup-campaign.json'
        self.report = {'status': 'running', 'acceptance': '100_clean+100_noisy+35_grid_all_success', 'batches': []}

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
                    pretraining_updates=min(5000 * batch, 20000), stop_on_success=True, corrective_demonstrations=True,
                    demonstration_job_id=self.demonstration_job_id if batch == 1 else None)
                self.report['batch'] = batch
                self.report['training_job_id'] = training['id']
                trained = self.wait(training['id'], 'training')
                if not trained.get('result', {}).get('training_candidate_qualified', False):
                    self.report['batches'].append({'training_job_id': training['id'],
                        'candidate_qualified': False, 'plateau': trained.get('result', {}).get('training_plateau', False)})
                    previous = training['id']
                    self.save()
                    continue
                suites = []
                for index, (suite, rounds) in enumerate((('clean', 100), ('noisy', 100), ('grid', 35))):
                    evaluation = self.client.rollout_onnx(training['id'], rounds=rounds,
                        seed=30261103 + batch * 10 + index, suite=suite)
                    self.report['evaluation_job_id'] = evaluation['id']
                    self.report['evaluation_suite'] = suite
                    result = self.wait(evaluation['id'], 'evaluation')
                    suites.append({'suite': suite, 'job_id': evaluation['id'],
                        'successes': result.get('successes', 0), 'rounds': rounds})
                self.report['batches'].append({'training_job_id': training['id'], 'suites': suites})
                self.save()
                if all(item['successes'] == item['rounds'] for item in suites):
                    self.report.update(status='succeeded', successful_model_job_id=training['id'],
                        success_rate=1., robust_grasp_validated=True, task_success_validated=True,
                        qualification_scope='defined_simulation_workspace_and_noise_only')
                    self.save()
                    return
                previous = training['id']
        except Exception as error:
            self.report.update(status='failed', error=str(error))
            self.save()
            raise


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--demonstration-job-id')
    args = parser.parse_args()
    PickupTrainingCampaign(args.demonstration_job_id).run()

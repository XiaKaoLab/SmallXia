"""通过现有任务宿主运行独立 SAC 学习器、table 执行者及视觉奖励训练。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import random
import os
from urllib.request import Request, urlopen
import sys
from pathlib import Path
from threading import Thread
from time import monotonic, sleep, time_ns

from ..imitation.api_worker import ImitationWorker
from .preprocessing import RLPreprocessor
from .replay import ReplayStore


class ReinforcementWorker(ImitationWorker):
    @staticmethod
    def http(path, body=None):
        request = Request('http://127.0.0.1:8766' + path,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    def store(self):
        return ReplayStore(Path(self.request['session_directory']))

    def learner(self):
        import torch
        from .learning import SACLearner
        store = self.store()
        preprocess = RLPreprocessor(store.config, self.request['device'])
        learner = SACLearner(store.config, self.request['device'])
        learner.publish(self.directory, 0)
        demonstrations = [ReplayStore(Path(path)) for path in self.request['demonstration_directories']]
        offline = [row for source in demonstrations for row in source.rows()
                   if row['kind'] == 'demonstration' or row['intervention']]
        last_data = monotonic()
        last_count = -1
        refresh_at = 0
        rows = []
        for step in range(self.request['steps']):
            while True:
                if store.control()['status'] == 'stopped':
                    return {'updates': step, 'stopped': True, 'physical': False}
                if monotonic() >= refresh_at:
                    rows = store.rows()
                    refresh_at = monotonic() + 1
                    if len(rows) != last_count:
                        last_data, last_count = monotonic(), len(rows)
                if len(rows) + len(offline) >= 2:
                    break
                self.progress(phase='waiting_for_transitions', transitions=len(rows), step=step)
                if monotonic() - last_data > self.request['idle_timeout_s']:
                    raise TimeoutError('等待至少两个转换样本超时，请先记录示教或启动执行者')
                sleep(0.2)
            demo = offline + [row for row in rows if row['kind'] == 'demonstration' or row['intervention']]
            online = [row for row in rows if row['kind'] == 'online' and not row['intervention']]
            size = self.request['batch_size']
            if demo and online:
                selected = random.choices(demo, k=size // 2) + random.choices(online, k=size - size // 2)
            else:
                selected = random.choices(demo or online, k=size)
            batch = {'state': preprocess.batch([row['observation'] for row in selected]),
                     'next_state': preprocess.batch([row['next_observation'] for row in selected]),
                     'action': torch.tensor([row['action'] for row in selected], dtype=torch.float32, device=self.request['device']),
                     'reward': torch.tensor([row['reward'] for row in selected], dtype=torch.float32, device=self.request['device']),
                     # 时间截断仍 bootstrap；真正成功/失败终止才置 done。
                     'done': torch.tensor([row['terminated'] for row in selected], dtype=torch.float32, device=self.request['device'])}
            metrics = learner.update(batch)
            self.progress(phase='learning', step=step + 1, total_steps=self.request['steps'], transitions=len(rows), **metrics)
            if (step + 1) % self.request['checkpoint_interval'] == 0:
                learner.publish(self.directory, step + 1)
        checkpoint = learner.publish(self.directory, self.request['steps'])
        return {'updates': self.request['steps'], 'checkpoint': checkpoint, 'backend': 'lerobot_sac',
                'physical': False, 'task_success_validated': False}

    def reward(self):
        import torch
        from .learning import reward_network
        store = self.store()
        preprocess = RLPreprocessor(store.config, self.request['device'])
        model = reward_network(len(store.config['cameras'])).to(self.request['device'])
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        labels = self.request['labels_snapshot']
        positives = [row for row in labels if row['reward'] == 1]
        negatives = [row for row in labels if row['reward'] == 0]
        for step in range(self.request['steps']):
            size = self.request['batch_size']
            selected = random.choices(positives, k=size // 2) + random.choices(negatives, k=size - size // 2)
            images = torch.stack([preprocess.reward_image(row['observation']) for row in selected]).to(self.request['device'])
            targets = torch.tensor([row['reward'] for row in selected], dtype=torch.float32, device=self.request['device'])
            loss = torch.nn.functional.binary_cross_entropy_with_logits(model(images).flatten(), targets)
            if not torch.isfinite(loss):
                raise ValueError('奖励分类器损失非有限值')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            self.progress(step=step + 1, total_steps=self.request['steps'], loss=float(loss.detach().cpu()))
        torch.save(model.cpu().state_dict(), self.directory / 'reward.pt')
        return {'checkpoint': str(self.directory / 'reward.pt'), 'labels': len(labels),
                'architecture': 'local_cnn', 'quality_validated': False}

    def actor(self, execute=True):
        import torch
        from .learning import make_policy, reward_network
        store = self.store()
        preprocess = RLPreprocessor(store.config, self.request['device'])
        policy = make_policy(store.config, self.request['device']).eval()
        learner = Path(self.request['learner_directory'])
        reward = None
        if 'reward_directory' in self.request:
            reward = reward_network(len(store.config['cameras'])).to(self.request['device']).eval()
            reward.load_state_dict(torch.load(Path(self.request['reward_directory']) / 'reward.pt', weights_only=True, map_location=self.request['device']))
        version = -1
        deadline = monotonic() + 60
        executed = 0
        for step in range(self.request['steps']):
            while not (learner / 'weights.json').exists():
                self.progress(phase='waiting_for_policy')
                if monotonic() > deadline:
                    raise TimeoutError('学习器未发布初始权重')
                sleep(0.2)
            if execute and store.control()['status'] != 'ready':
                break
            started = monotonic()
            weights = json.loads((learner / 'weights.json').read_text(encoding='utf-8'))
            if weights['step'] != version:
                for attempt in range(3):
                    try:
                        policy.load_state_dict(torch.load(learner / weights['file'], weights_only=True, map_location=self.request['device']))
                        version = weights['step']
                        break
                    except FileNotFoundError:
                        if attempt == 2:
                            raise
                        weights = json.loads((learner / 'weights.json').read_text(encoding='utf-8'))
            observed = self.http(f"/api/v1/reinforcement/sessions/{store.config['id']}/observation")
            with torch.inference_mode():
                action = policy.select_action(preprocess.batch([observed]))[0].cpu().tolist()
            if not execute:
                return {'action': action, 'action_space': 'normalized_joint_delta', 'policy_version': version, 'executed': False, 'physical': False}
            result = self.http(f"/api/v1/reinforcement/sessions/{store.config['id']}/step", {'action': action})
            executed += 1
            if reward is not None:
                image = preprocess.reward_image(result['observation']).unsqueeze(0).to(self.request['device'])
                with torch.inference_mode():
                    probability = float(torch.sigmoid(reward(image)[0, 0]).cpu())
                if probability >= self.request['success_threshold'] and store.control()['status'] == 'ready':
                    self.http(f"/api/v1/reinforcement/sessions/{store.config['id']}/feedback",
                              {'success': True, 'transition_id': result['transition_id'], 'reward_source': 'classifier'})
            self.progress(step=step + 1, total_steps=self.request['steps'], policy_version=version, last_transition_id=result['transition_id'])
            sleep(max(0, 1 / store.config['fps'] - (monotonic() - started)))
        return {'steps': executed, 'episode_status': store.control()['status'], 'physical': False, 'target': 'table', 'task_success_validated': False}

    def run(self):
        Thread(target=self.watch_parent, daemon=True).start()
        self.progress(status='running', started_at_ns=time_ns())
        try:
            if self.request['kind'] == 'ball_pickup':
                from .ball_training import BallPickupTraining
                result = BallPickupTraining(self).run()
                self.progress(status='succeeded', phase='completed', progress=1, result=result, finished_at_ns=time_ns())
                return
            methods = {'learner': self.learner, 'actor': self.actor, 'reward': self.reward, 'predict': lambda: self.actor(execute=False)}
            result = methods[self.request['kind']]()
            self.progress(status='succeeded', result=result, finished_at_ns=time_ns())
        except Exception as error:
            self.progress(status='failed', error=f'{type(error).__name__}: {error}', finished_at_ns=time_ns())
            raise


if __name__ == '__main__':
    ReinforcementWorker(Path(sys.argv[1])).run()

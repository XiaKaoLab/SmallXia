"""批量采集独立小球抓取环境，更新 SAC 策略并发布真实回合分数与进度。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
from time import monotonic

import numpy as np

from .ball_environment import BallPickupEnvironment
from .learning import SACLearner
from ..imitation.api_jobs import atomic_json


class BallPickupTraining:
    def __init__(self, worker):
        self.worker = worker
        self.request = worker.request

    def run(self):
        import torch
        torch.set_num_threads(4)
        count, rounds = self.request['num_envs'], self.request['rounds']
        atomic_json(self.worker.directory / 'policy_config.json', {'task': 'ball_pickup', 'cameras': [],
            'state_dim': 18, 'state_order': 'joint_positions_6,joint_velocities_6,ball_xyz_3,ball_minus_tip_xyz_3',
            'action_space': 'normalized_joint_delta', 'action_scale': .08, 'num_envs': count, 'rounds': rounds,
            'seed': self.request['seed'], 'physical': False})
        self.worker.progress(phase='initializing', task='拿取小球', num_envs=count, rounds=rounds,
                             completed_episodes=0, total_episodes=count * rounds, progress=0, score=None,
                             score_source='episode_return', successes=0, physical=False)
        seed = self.request['seed']
        torch.manual_seed(seed)
        rng = random.Random(seed)
        urdf = Path(__file__).resolve().parents[4] / 'table/public/robots/so101/so101_new_calib.urdf'
        environments = BallPickupEnvironment.vector(urdf, count, seed)
        try:
            learner = SACLearner({'cameras': [], 'state_dim': 18}, self.request['device'])
            replay = deque(maxlen=50000)
            scores = deque(maxlen=100)
            completed = [0] * count
            states = [env.state() for env in environments]
            successes = updates = transitions = 0
            last_publish = 0
            metrics = {}
            self.worker.progress(phase='collecting', snapshot=environments[0].snapshot())
            with ThreadPoolExecutor(max_workers=min(count, 8)) as pool:
                while min(completed) < rounds:
                    active = [index for index in range(count) if completed[index] < rounds]
                    observations = torch.as_tensor(np.stack([states[index] for index in active]), device=self.request['device'])
                    learner.policy.eval()
                    if transitions < 64:
                        actions = np.asarray([[rng.uniform(-1, 1) for _ in range(6)] for _ in active], dtype=np.float32)
                    else:
                        with torch.inference_mode():
                            # 训练采集使用随机策略采样；不能使用评估阶段的确定性均值。
                            distribution = learner.policy.actor({'observation.state': observations})
                            actions = distribution[0].detach().cpu().numpy()
                    futures = [pool.submit(environments[index].advance, actions[offset]) for offset, index in enumerate(active)]
                    for offset, index in enumerate(active):
                        state, reward, terminated, truncated, success = futures[offset].result()
                        replay.append((states[index], actions[offset], reward, state, terminated))
                        transitions += 1
                        states[index] = state
                        if terminated or truncated:
                            scores.append(environments[index].return_)
                            completed[index] += 1
                            successes += int(success)
                            if completed[index] < rounds:
                                states[index] = environments[index].reset_episode()
                    if len(replay) >= 64:
                        selected = rng.sample(list(replay), 64)
                        tensor = lambda values: torch.as_tensor(np.asarray(values), dtype=torch.float32, device=self.request['device'])
                        metrics = learner.update({'state': {'observation.state': tensor([row[0] for row in selected])},
                            'action': tensor([row[1] for row in selected]), 'reward': tensor([row[2] for row in selected]),
                            'next_state': {'observation.state': tensor([row[3] for row in selected])},
                            'done': tensor([row[4] for row in selected])})
                        updates += 1
                        if updates % 200 == 0:
                            learner.publish(self.worker.directory, updates)
                    if monotonic() - last_publish >= .5 or min(completed) >= rounds:
                        done = sum(completed)
                        self.worker.progress(phase='learning' if updates else 'collecting', completed_episodes=done,
                            progress=done / (count * rounds), score=float(np.mean(scores)) if scores else None,
                            current_score=float(environments[0].return_), successes=successes, success_rate=successes / done if done else 0,
                            env_rounds=completed, transitions=transitions, updates=updates,
                            snapshot=environments[0].snapshot(), **metrics)
                        last_publish = monotonic()
            checkpoint = learner.publish(self.worker.directory, updates)
            self.worker.progress(phase='exporting')
            from .onnx_export import BallOnnxExporter
            exported = BallOnnxExporter().export(Path(checkpoint), self.worker.directory, policy=learner.policy)
            return {'checkpoint': checkpoint, **exported, 'completed_episodes': sum(completed), 'successes': successes,
                    'score': float(np.mean(scores)), 'updates': updates, 'physical': False, 'task_success_validated': successes > 0}
        finally:
            for env in environments:
                env.disconnect()

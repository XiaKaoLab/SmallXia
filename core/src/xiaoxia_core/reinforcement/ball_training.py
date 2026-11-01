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
from .ball_observation import BallObservation
from .ball_demonstration import BallDemonstrator
from ..imitation.api_jobs import atomic_json
from .preview import TrainingPreviewPublisher


class BallPickupTraining:
    def __init__(self, worker):
        self.worker = worker
        self.request = worker.request

    def run(self):
        import torch
        torch.set_num_threads(4)
        count, rounds = self.request['num_envs'], self.request['rounds']
        atomic_json(self.worker.directory / 'policy_config.json', {'task': 'ball_pickup', 'cameras': ['wrist'],
            'environment_version': BallPickupEnvironment.version,
            'state_dim': 18, 'state_order': 'joint_positions_6,joint_velocities_6,ball_xyz_3,ball_minus_tip_xyz_3',
            'action_space': 'normalized_joint_delta', 'action_scale': .08, 'num_envs': count, 'rounds': rounds,
            'observation_noise': BallObservation.noise, 'demonstration_episodes': 8,
            'privileged_state': True, 'seed': self.request['seed'], 'physical': False})
        self.worker.progress(phase='initializing', task='拿取小球', num_envs=count, rounds=rounds,
                             environment_version=BallPickupEnvironment.version,
                             completed_episodes=0, total_episodes=count * rounds, progress=0, score=None,
                             score_source='episode_return', successes=0, physical=False)
        seed = self.request['seed']
        torch.manual_seed(seed)
        rng = random.Random(seed)
        urdf = Path(__file__).resolve().parents[4] / 'table/public/robots/so101/so101_new_calib.urdf'
        environments = BallPickupEnvironment.vector(urdf, count, seed)
        observers = []
        try:
            for i, env in enumerate(environments):
                observers.append(BallObservation(env, seed + 100000 + i))
            learner = SACLearner({'cameras': ['wrist'], 'state_dim': 18}, self.request['device'])
            if self.request.get('warm_start_checkpoint'):
                learner.policy.load_state_dict(torch.load(self.request['warm_start_checkpoint'], map_location=self.request['device'], weights_only=True))
            preview = TrainingPreviewPublisher(self.worker.directory)
            self.worker.progress(reward_config=environments[0].reward.description())
            preview.publish(environments, force=True)
            replay = deque(maxlen=5000)
            demos = []
            self.worker.progress(phase='demonstrating', demonstration_successes=0)
            teacher = BallDemonstrator()
            demo_successes = 0
            for attempt in range(24):
                env, observer = environments[0], observers[0]
                env.reset_episode()
                trajectory = teacher.collect(env, observer)
                if not trajectory:
                    continue
                demo_successes += 1
                demos.extend(trajectory)
                preview.publish(environments, force=True)
                self.worker.progress(demonstration_successes=demo_successes, demonstration_transitions=len(demos))
                if demo_successes == 8:
                    break
            if demo_successes < 8:
                raise ValueError('24 次尝试未取得 8 轮成功示教，停止训练并检查物理/IK')
            np.savez_compressed(self.worker.directory / 'demonstrations.npz',
                state=np.stack([r[0]['observation.state'] for r in demos]),
                wrist=np.stack([r[0][BallObservation.camera_key] for r in demos]),
                action=np.stack([r[1] for r in demos]), reward=np.asarray([r[2] for r in demos]),
                next_state=np.stack([r[3]['observation.state'] for r in demos]),
                next_wrist=np.stack([r[3][BallObservation.camera_key] for r in demos]),
                done=np.asarray([r[4] for r in demos]))
            self.worker.progress(phase='pretraining')
            for step in range(200):
                selected = rng.sample(demos, min(64, len(demos)))
                learner.behavior_clone(BallObservation.batch([r[0] for r in selected], self.request['device']),
                    torch.as_tensor(np.stack([r[1] for r in selected]), device=self.request['device']))
            for env in environments:
                env.reset_episode()
            scores = deque(maxlen=100)
            completed = [0] * count
            states = [observer.read() for observer in observers]
            successes = updates = transitions = 0
            last_publish = 0
            metrics = {}
            self.worker.progress(phase='collecting', snapshot=environments[0].snapshot())
            with ThreadPoolExecutor(max_workers=min(count, 8)) as pool:
                while min(completed) < rounds:
                    active = [index for index in range(count) if completed[index] < rounds]
                    observations = BallObservation.batch([states[index] for index in active], self.request['device'])
                    learner.policy.eval()
                    with torch.inference_mode():
                        distribution = learner.policy.actor(observations)
                        actions = distribution[0].detach().cpu().numpy()
                    futures = [pool.submit(environments[index].advance, actions[offset]) for offset, index in enumerate(active)]
                    for offset, index in enumerate(active):
                        state, reward, terminated, truncated, success = futures[offset].result()
                        state = observers[index].read()
                        replay.append((states[index], actions[offset], reward, state, terminated))
                        transitions += 1
                        states[index] = state
                        if terminated or truncated:
                            scores.append(environments[index].return_)
                            completed[index] += 1
                            successes += int(success)
                            if completed[index] < rounds:
                                environments[index].reset_episode()
                                states[index] = observers[index].read()
                    if len(replay) >= 64:
                        selected = rng.sample(list(replay), 48) + rng.sample(demos, 16)
                        tensor = lambda values: torch.as_tensor(np.asarray(values), dtype=torch.float32, device=self.request['device'])
                        metrics = learner.update({'state': BallObservation.batch([row[0] for row in selected], self.request['device']),
                            'action': tensor([row[1] for row in selected]), 'reward': tensor([row[2] for row in selected]),
                            'next_state': BallObservation.batch([row[3] for row in selected], self.request['device']),
                            'done': tensor([row[4] for row in selected])})
                        metrics['loss_bc'] = learner.behavior_clone(
                            BallObservation.batch([r[0] for r in selected[-16:]], self.request['device']),
                            tensor([r[1] for r in selected[-16:]]))
                        updates += 1
                        if updates % 200 == 0:
                            learner.publish(self.worker.directory, updates)
                    preview.publish(environments)
                    if monotonic() - last_publish >= .5 or min(completed) >= rounds:
                        done = sum(completed)
                        self.worker.progress(phase='learning' if updates else 'collecting', completed_episodes=done,
                            progress=done / (count * rounds), score=float(np.mean(scores)) if scores else None,
                            current_score=float(environments[0].return_), successes=successes, success_rate=successes / done if done else 0,
                            reward_terms=environments[0].last_reward_terms,
                            env_rounds=completed, transitions=transitions, updates=updates,
                            snapshot=environments[0].snapshot(), **metrics)
                        last_publish = monotonic()
            checkpoint = learner.publish(self.worker.directory, updates)
            preview.publish(environments, force=True)
            self.worker.progress(phase='exporting')
            from .onnx_export import BallOnnxExporter
            exported = BallOnnxExporter().export(Path(checkpoint), self.worker.directory, policy=learner.policy, config=BallObservation.config, environment_version=BallPickupEnvironment.version)
            return {'checkpoint': checkpoint, **exported, 'completed_episodes': sum(completed), 'successes': successes,
                    'score': float(np.mean(scores)), 'updates': updates, 'physical': False, 'task_success_validated': successes > 0}
        finally:
            for observer in observers:
                observer.close()
            for env in environments:
                env.disconnect()

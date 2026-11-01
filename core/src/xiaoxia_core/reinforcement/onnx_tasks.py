"""执行 ONNX 导出或仅用 ONNX Runtime 驱动抓球仿真，不更新训练参数。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from collections import deque
from pathlib import Path
from time import monotonic

import numpy as np


class BallOnnxTasks:
    def __init__(self, worker):
        self.worker, self.request = worker, worker.request

    def export(self):
        from .onnx_export import BallOnnxExporter
        self.worker.progress(phase='exporting')
        return BallOnnxExporter().from_directory(Path(self.request['source_directory']), self.worker.directory)

    def rollout(self):
        from ..inference.ball_onnx import BallOnnxPolicy
        from .ball_environment import BallPickupEnvironment
        policy = BallOnnxPolicy(Path(self.request['source_directory']))
        if policy.manifest.get('environment_version') != BallPickupEnvironment.version:
            raise ValueError('抓球碰撞、观测和奖励环境已更新，旧模型不能作为新版环境的有效推理模型，请重新训练')
        urdf = Path(__file__).resolve().parents[4] / 'table/public/robots/so101/so101_new_calib.urdf'
        env = BallPickupEnvironment.vector(urdf, 1, self.request['seed'])[0]
        from .ball_observation import BallObservation
        observer = BallObservation(env, self.request['seed'] + 100000, noisy=self.request.get('suite') == 'noisy') if policy.manifest.get('cameras') else None
        from .preview import TrainingPreviewPublisher
        preview = TrainingPreviewPublisher(self.worker.directory)
        preview.publish([env], force=True)
        rounds = self.request['rounds']
        positions = [(float(x), float(y)) for x in np.linspace(.16, .23, 7)
                     for y in np.linspace(-.05, .05, 5)] if self.request.get('suite') == 'grid' else None
        episodes = []
        scores = deque(maxlen=100)
        successes = transitions = 0
        last_publish = 0
        try:
            for episode in range(rounds):
                state = env.reset_episode(position=positions[episode] if positions else None)
                peak_floor_force = 0.
                while True:
                    observation = observer.read() if observer else None
                    action = policy.predict(np.asarray([observation['observation.state'] if observation else state]),
                        np.asarray([observation[BallObservation.camera_key]], dtype=np.float32) / 255 if observation else None)[0]
                    state, _, terminated, truncated, success = env.advance(action)
                    if observer:
                        observer.read()  # 将当前动作后的相机发现奖励计入回合分数。
                    peak_floor_force = max(peak_floor_force, env.contact_state()['arm_floor_force'])
                    transitions += 1
                    preview.publish([env])
                    done = terminated or truncated
                    if done:
                        scores.append(env.return_)
                        accepted = bool(success and peak_floor_force <= 5.)
                        successes += int(accepted)
                        episodes.append({'success': accepted, 'physical_grasp': bool(success),
                            'peak_arm_floor_force': peak_floor_force, 'snapshot': env.snapshot()})
                    if monotonic() - last_publish >= .5 or done:
                        completed = episode + int(done)
                        self.worker.progress(phase='inferencing', runtime='onnxruntime', completed_episodes=completed,
                            progress=completed / rounds, score=float(np.mean(scores)) if scores else None,
                            current_score=float(env.return_), successes=successes, transitions=transitions,
                            success_rate=successes / completed if completed else 0,
                            snapshot=env.snapshot(), physical=False)
                        last_publish = monotonic()
                    if done:
                        break
            preview.publish([env], force=True)
            return {'runtime': 'onnxruntime', 'completed_episodes': rounds, 'score': float(np.mean(scores)),
                    'successes': successes, 'transitions': transitions, 'training': False, 'physical': False, 'suite': self.request.get('suite', 'clean'),
                    'episodes': episodes, 'all_passed': successes == rounds}
        finally:
            if observer:
                observer.close()
            env.disconnect()

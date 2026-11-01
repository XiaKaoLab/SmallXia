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
        urdf = Path(__file__).resolve().parents[4] / 'table/public/robots/so101/so101_new_calib.urdf'
        env = BallPickupEnvironment.vector(urdf, 1, self.request['seed'])[0]
        from .preview import TrainingPreviewPublisher
        preview = TrainingPreviewPublisher(self.worker.directory)
        preview.publish([env], force=True)
        rounds = self.request['rounds']
        scores = deque(maxlen=100)
        successes = transitions = 0
        last_publish = 0
        try:
            for episode in range(rounds):
                state = env.reset_episode()
                while True:
                    action = policy.predict(np.asarray([state]))[0]
                    state, _, terminated, truncated, success = env.advance(action)
                    transitions += 1
                    preview.publish([env])
                    done = terminated or truncated
                    if done:
                        scores.append(env.return_)
                        successes += int(success)
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
                    'successes': successes, 'transitions': transitions, 'training': False, 'physical': False}
        finally:
            env.disconnect()

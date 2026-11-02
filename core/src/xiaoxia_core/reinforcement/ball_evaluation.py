"""使用独立随机位置评估确定性学习策略，不调用示教控制器、不更新参数。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import numpy as np
import torch
from .ball_environment import BallPickupEnvironment
from .ball_observation import BallObservation


class BallPolicyEvaluation:
    def __init__(self, urdf, device):
        self.urdf, self.device = urdf, device

    def run(self, policy, rounds=20, seed=20261102, preview=None, level=2, noisy=False):
        env = BallPickupEnvironment.vector(self.urdf, 1, seed)[0]
        env.curriculum_level = level
        env.reset_episode()
        observer = None
        results = []
        policy.eval()
        try:
            observer = BallObservation(env, seed + 100000, noisy=noisy)
            for episode in range(rounds):
                if episode:
                    env.reset_episode()
                success = False
                peak_floor_force = 0.
                closest_distance = float(np.linalg.norm(env.state()[15:18]))
                phase_counts = {}
                max_lift = 0.
                while not env.ended:
                    observation = observer.read()
                    batch = observer.batch([observation], self.device)
                    with torch.inference_mode():
                        actor = policy.actor
                        action = torch.tanh(actor.mean_layer(actor.network(actor.encoder(batch))))[0].cpu().numpy()
                    _, _, _, _, success = env.advance(action)
                    observer.read()
                    phase_counts[env.phases.name] = phase_counts.get(env.phases.name, 0) + 1
                    closest_distance = min(closest_distance, float(np.linalg.norm(env.state()[15:18])))
                    max_lift = max(max_lift, float(env.ball_position()[2] - env.spawn_position[2]))
                    peak_floor_force = max(peak_floor_force, env.contact_state()['arm_floor_force'])
                    if preview:
                        preview.set_camera_frame(observation[BallObservation.camera_key], float(env._data.time))
                        preview.publish([env])
                results.append({'success': bool(success and peak_floor_force <= 5.), 'peak_arm_floor_force': peak_floor_force, 'score': env.return_,
                    'held_seconds': env.held_seconds, 'closest_distance_m': closest_distance,
                    'max_lift_m': max_lift, 'phase_steps': phase_counts,
                    'failure_stage': None if success and peak_floor_force <= 5. else env.phases.name, 'snapshot': env.snapshot()})
            return {'rounds': rounds, 'seed': seed, 'successes': sum(row['success'] for row in results),
                'score': float(np.mean([row['score'] for row in results])), 'episodes': results,
                'curriculum_level': level, 'noisy': noisy, 'controller': 'learned_actor_with_phase_gate', 'physical': False}
        finally:
            if observer:
                observer.close()
            env.disconnect()

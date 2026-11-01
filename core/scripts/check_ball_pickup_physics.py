"""检查抓球的真实双指接触、持续抬升、松手落球和每轮重置；不训练或连接实机。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy.optimize import least_squares

from xiaoxia_core.contracts import Action
from xiaoxia_core.reinforcement.ball_environment import BallPickupEnvironment
from xiaoxia_core.safety import JOINTS


class PickupPhysicsCheck:
    def __init__(self, urdf):
        self.urdf = urdf

    def solve(self, env, target, opening):
        model, data = env._state()
        trial = mujoco.MjData(model)
        trial.qpos[:] = data.qpos
        addresses = [model.jnt_qposadr[env._joints[name]] for name in JOINTS]
        bounds = ([env.limits.joints[name].lower + .001 for name in JOINTS[:5]],
                  [env.limits.joints[name].upper - .001 for name in JOINTS[:5]])

        def residual(q):
            trial.qpos[addresses[:5]] = q
            trial.qpos[addresses[5]] = opening
            mujoco.mj_forward(model, trial)
            return np.concatenate([(trial.site_xpos[env.tip] - target) * 10,
                trial.site_xmat[env.tip].reshape(3, 3)[:, 2] - [0, 0, 1], [.02 * (q[4] - start[4])]])

        start = np.clip(data.qpos[addresses[:5]], np.asarray(bounds[0]) + 1e-6, np.asarray(bounds[1]) - 1e-6)
        solved = least_squares(residual, start, bounds=bounds, max_nfev=150)
        if np.linalg.norm(residual(solved.x)[:3]) > .03:
            raise ValueError('参考抓取位姿不可达，位置误差超过 3mm')
        return np.r_[solved.x, opening]

    def run(self, seed):
        env = BallPickupEnvironment.vector(self.urdf, 1, seed)[0]
        trace, success = [], False
        initial = env.ball_position().copy()
        grasp_angle = None
        try:
            for stage, height, opening, steps in [('approach', initial[2] + .065, 1.0, 28),
                ('descend', initial[2] + .002, 1.0, 18), ('close', initial[2] + .002, -.16, 18),
                ('lift', initial[2] + .075, -.16, 34)]:
                target = np.array([initial[0], initial[1], height])
                if stage == 'lift' and grasp_angle is not None:
                    opening = grasp_angle
                q = self.solve(env, target, opening)
                for _ in range(steps):
                    current = np.array([env.read_observation().joint_positions[name] for name in JOINTS])
                    _, reward, terminated, truncated, success = env.advance(np.clip((q - current) / .08, -1, 1))
                    trace.append({'stage': stage, 'reward': reward, **env.snapshot()})
                    if stage == 'close' and env.contact_state()['both_jaws']:
                        grasp_angle = env.read_observation().joint_positions['gripper'] - .02
                        break
                    if terminated or truncated:
                        break
                if env.ended:
                    break
            held_position = env.ball_position().copy()
            release = env.read_observation().joint_positions
            release['gripper'] = 1.0
            env.send_action(Action(release))
            for _ in range(12):
                env._physics_step(track_hold=False)
            released = env.ball_position().copy()
            dropped = held_position[2] - released[2] > .03 and env.contact_state()['ball_on_floor']
            reset = []
            for _ in range(3):
                env.reset_episode()
                reset.append({'position': env.ball_position().tolist(), 'velocity': env._data.qvel.tolist(),
                    'score': env.return_, 'held_seconds': env.held_seconds, 'episode': env.episode_index})
            return {'seed': seed, 'success': success, 'lift_m': float(held_position[2] - initial[2]),
                'released_drop_m': float(held_position[2] - released[2]), 'released_to_floor': bool(dropped),
                'initial_position': initial.tolist(), 'resets': reset, 'trace': trace, 'physical': False}
        finally:
            env.disconnect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', type=int, nargs='+', default=[42])
    parser.add_argument('--output', type=Path, default=Path('data/runtime/pickup-physics-check.json'))
    args = parser.parse_args()
    urdf = Path(__file__).resolve().parents[2] / 'table/public/robots/so101/so101_new_calib.urdf'
    results = [PickupPhysicsCheck(urdf).run(seed) for seed in args.seeds]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{key: value for key, value in result.items() if key != 'trace'} for result in results], ensure_ascii=False))

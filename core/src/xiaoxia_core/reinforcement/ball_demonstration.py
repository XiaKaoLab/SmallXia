"""用物理接触和 IK 生成成功示教；仅成功轨迹进入示教回放。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import mujoco
import numpy as np
import torch
from ..safety import JOINTS


class BallDemonstrator:
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
        # 使用现有 Torch 求解小型阻尼最小二乘，避免 base 环境 SciPy/MKL 与 Torch 的双 OpenMP 冲突。
        q = start.copy()
        damping = .001
        for _ in range(150):
            error = residual(q)
            jacobian = np.stack([(residual(q + np.eye(5)[i] * 1e-5) - error) / 1e-5 for i in range(5)], axis=1)
            jac = torch.from_numpy(jacobian)
            delta = torch.linalg.solve(jac.T @ jac + damping * torch.eye(5, dtype=torch.float64),
                                       -jac.T @ torch.from_numpy(error)).numpy()
            candidate = np.clip(q + np.clip(delta, -.2, .2), bounds[0], bounds[1])
            if float(np.sum(residual(candidate) ** 2)) < float(np.sum(error ** 2)):
                q = candidate
                damping = max(damping / 2, 1e-6)
            else:
                damping = min(damping * 4, 1e4)
            if np.max(np.abs(delta)) < 1e-6:
                break
        if float(np.sqrt(np.sum(residual(q)[:3] ** 2))) > .03:
            raise ValueError('参考抓取位姿不可达，位置误差超过 3mm')
        return np.r_[q, opening]

    def expert_action(self, env, cache):
        phase = env.phases.name
        current = np.array([env.read_observation().joint_positions[name] for name in JOINTS])
        if cache.get('phase') != phase:
            heights = {'search': .065, 'approach': .065, 'align': .002, 'close': .002,
                       'lift': .075, 'hold': .075, 'recover': .065}
            opening = 1. if phase in ('search', 'approach', 'align', 'recover') else -.16
            if phase in ('lift', 'hold'):
                opening = cache.setdefault('grasp_angle', current[5] - .02)
            elif phase == 'recover':
                cache.pop('grasp_angle', None)
            target = env.ball_position().copy()
            target[2] = env.spawn_position[2] + heights[phase]
            cache.update(phase=phase, target=self.solve(env, target, opening))
        return np.clip((cache['target'] - current) / .08, -1, 1).astype(np.float32)

    def collect(self, env, observer):
        rows, cache = [], {}
        observation = observer.read()
        success = False
        while not env.ended:
            action = self.expert_action(env, cache)
            _, reward, terminated, _, success = env.advance(action)
            following = observer.read()
            rows.append((observation, action, reward + env.last_visual_reward, following, terminated))
            observation = following
        return rows if success else []

    def corrections(self, env, observer, policy, device, preview=None):
        labels, cache = [], {}
        policy.eval()
        while not env.ended:
            observation = observer.read()
            expert = self.expert_action(env, cache)
            labels.append((observation, expert))
            with torch.inference_mode():
                batch = observer.batch([observation], device)
                actor = policy.actor
                predicted = torch.tanh(actor.mean_layer(actor.network(actor.encoder(batch))))[0].cpu().numpy()
            env.advance(np.clip(.7 * expert + .3 * predicted, -1, 1))
            observer.read()
            if preview:
                preview.publish([env])
        return labels

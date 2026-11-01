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

    def collect(self, env, observer):
        initial = env.ball_position().copy()
        rows, grasp_angle = [], None
        observation = observer.read()
        success = False
        for stage, height, opening, steps in [('approach', .065, 1., 28),
                ('descend', .002, 1., 18), ('close', .002, -.16, 18), ('lift', .075, -.16, 34)]:
            if stage == 'lift' and grasp_angle is not None:
                opening = grasp_angle
            target = initial + [0, 0, height]
            q = self.solve(env, target, opening)
            for _ in range(steps):
                current = np.array([env.read_observation().joint_positions[name] for name in JOINTS])
                action = np.clip((q - current) / .08, -1, 1).astype(np.float32)
                _, reward, terminated, truncated, success = env.advance(action)
                following = observer.read()
                reward += env.last_visual_reward
                # 不用定时等待帧教策略在接近/下降的阶段交界永久停住。
                if stage not in ('approach', 'descend') or np.max(np.abs(action)) >= .04:
                    rows.append((observation, action, reward, following, terminated))
                observation = following
                if terminated or truncated:
                    break
                if stage == 'close' and env.contact_state()['both_jaws']:
                    grasp_angle = env.read_observation().joint_positions['gripper'] - .02
                    break
            if env.ended:
                break
        return rows if success else []

    def corrections(self, env, observer, policy, device, preview=None):
        # DAgger：在模型偏离示教后的实际状态标注专家动作，仅用于行为克隆。
        # 混合执行动作不会写入 SAC 示教回放，避免伪造 action/next_state 转换。
        initial = env.ball_position().copy()
        labels = []
        stage, q, grasp_angle = 0, None, None
        heights = [.065, .002, .002, .075]
        openings = [1., 1., -.16, -.16]
        policy.eval()
        for _ in range(env.episode_steps):
            observation = observer.read()
            current = np.array([env.read_observation().joint_positions[name] for name in JOINTS])
            if q is None:
                target = initial + [0, 0, heights[stage]]
                q = self.solve(env, target, grasp_angle if stage == 3 and grasp_angle is not None else openings[stage])
            if stage < 2 and np.max(np.abs(q - current)) < .015:
                stage += 1
                q = None
                continue
            if stage == 2 and env.contact_state()['both_jaws']:
                grasp_angle = current[5] - .02
                stage, q = 3, None
                continue
            expert = np.clip((q - current) / .08, -1, 1).astype(np.float32)
            labels.append((observation, expert))
            with torch.inference_mode():
                batch = observer.batch([observation], device)
                actor = policy.actor
                predicted = torch.tanh(actor.mean_layer(actor.network(actor.encoder(batch))))[0].cpu().numpy()
            env.advance(np.clip(.7 * expert + .3 * predicted, -1, 1))
            observer.read()
            if preview:
                preview.publish([env])
            if env.ended:
                break
        return labels

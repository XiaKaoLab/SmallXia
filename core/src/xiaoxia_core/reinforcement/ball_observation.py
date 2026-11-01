"""抓球腕部 RGB 观测与可复现的传感器噪声；独立随机源不改变物理状态。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import mujoco
import numpy as np


class BallObservation:
    camera_key = 'observation.images.wrist'
    config = {'cameras': ['wrist'], 'state_dim': 31, 'shared_encoder': False,
              'state_order': 'joint_positions_6,joint_velocities_6,ball_xyz_3,ball_minus_tip_xyz_3,phase_onehot_7,jaw_forces_2,hold_fraction_1,orientation_error_3', 'actor_std_min': .01, 'actor_std_max': .1,
              'state_scale': [.5] * 6 + [.1] * 6 + [5.] * 3 + [20.] * 3 + [1.] * 13}
    noise = {'joint_position_std_rad': .002, 'joint_velocity_std': .005,
             'position_std_m': .001, 'rgb_std': .01, 'brightness_range': [.9, 1.1]}

    def __init__(self, env, seed, noisy=True):
        self.env, self.noisy = env, noisy
        self.random = np.random.default_rng(seed)
        self.renderer = mujoco.Renderer(env._model, height=64, width=64)

    def read(self):
        self.renderer.update_scene(self.env._data, camera='pickup_wrist')
        rgb = self.renderer.render().copy()
        self.env.observe_ball_image(rgb)
        image = rgb.astype(np.float32) / 255
        state = self.env.state().copy()
        if self.noisy:
            state += self.random.normal(0, [.002] * 6 + [.005] * 6 + [.001] * 6 + [0.] * 13)
            image = np.clip(image * self.random.uniform(.9, 1.1) + self.random.normal(0, .01, image.shape), 0, 1)
        return {'observation.state': state, self.camera_key: (image.transpose(2, 0, 1) * 255).round().astype(np.uint8)}

    @staticmethod
    def batch(observations, device):
        import torch
        batch = {key: torch.as_tensor(np.stack([row[key] for row in observations]), device=device,
                    dtype=torch.float32) / (255 if key.startswith('observation.images.') else 1)
                for key in observations[0]}
        batch['observation.state'] *= torch.tensor(BallObservation.config['state_scale'], device=device)
        return batch

    def close(self):
        self.renderer.close()

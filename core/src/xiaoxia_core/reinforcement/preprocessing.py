"""统一 SAC/奖励分类器的图像 ROI、缩放及六关节状态归一化。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import numpy as np
from PIL import Image

from ..safety import JOINTS


class RLPreprocessor:
    def __init__(self, config, device):
        self.config, self.device = config, device

    def image(self, path, camera):
        import torch
        with Image.open(path) as opened:
            image = opened.convert('RGB')
            roi = self.config['roi'].get(camera)
            if roi:
                top, left, height, width = roi
                if left + width > image.width or top + height > image.height:
                    raise ValueError('ROI 超出当前画面边界')
                image = image.crop((left, top, left + width, top + height))
            image = image.resize((64, 64))
            return torch.from_numpy(np.array(image, copy=True)).permute(2, 0, 1).float() / 255

    def observation(self, observation):
        import torch
        limits = self.config['limits']
        state = [2 * (observation['state'][joint] - limits[joint]['lower']) /
                 (limits[joint]['upper'] - limits[joint]['lower']) - 1 for joint in JOINTS]
        result = {'observation.state': torch.tensor(state, dtype=torch.float32)}
        for camera in self.config['cameras']:
            result[f'observation.images.{camera}'] = self.image(observation['images'][camera], camera)
        return result

    def batch(self, observations):
        import torch
        rows = [self.observation(observation) for observation in observations]
        return {key: torch.stack([row[key] for row in rows]).to(self.device) for key in rows[0]}

    def reward_image(self, observation):
        import torch
        return torch.cat([self.image(observation['images'][camera], camera) for camera in self.config['cameras']], dim=0)

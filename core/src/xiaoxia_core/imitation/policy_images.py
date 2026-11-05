"""功能：真实策略图像在内存解码和缩放，同轮复用同源画面并保留时间信息。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from time import time_ns
from ..collection.frame_client import CameraFrameClient


class PolicyImages:
    def __init__(self, metadata, sources):
        self.shapes = metadata['images']
        self.sources = sources
        self.client = CameraFrameClient()

    def read(self):
        if not self.shapes:
            return {}, {'camera_timestamps_ns': {}, 'camera_age_ms': {}}
        import numpy as np
        from PIL import Image
        frames, images, timestamps = {}, {}, {}
        for name, shape in self.shapes.items():
            source = self.sources.get(name, name)
            if source != 'real' and not source.startswith('opencv_'):
                raise ValueError('真机策略需要为模型图像选择真实摄像头')
            if source not in frames:
                frame = self.client.read(source)
                frames[source] = (self.client.rgb(frame), frame.get('timestamp_ns'))
            pixels, timestamp = frames[source]
            if list(pixels.shape) != shape:
                pixels = np.asarray(Image.fromarray(pixels).resize((shape[1], shape[0]), Image.Resampling.BILINEAR))
            images[name] = pixels
            timestamps[name] = timestamp
        now = time_ns()
        return images, {'camera_timestamps_ns': timestamps,
                        'camera_age_ms': {name: max(0, (now - stamp) / 1e6)
                                          for name, stamp in timestamps.items() if stamp is not None}}

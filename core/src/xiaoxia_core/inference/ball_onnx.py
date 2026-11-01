"""使用 ONNX Runtime 执行抓球策略，按 manifest 输入18/31维仿真状态，输出六轴归一化增量。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import hashlib
import json
from pathlib import Path

import numpy as np


class BallOnnxPolicy:
    def __init__(self, directory: Path):
        import onnxruntime as ort
        self.manifest = json.loads((directory / 'policy.onnx.json').read_text(encoding='utf-8'))
        if self.manifest.get('task') != 'ball_pickup' or self.manifest.get('state_dim') not in (18, 31):
            raise ValueError('ONNX 不是已定义的抓球观测模型')
        self.state_dim = self.manifest['state_dim']
        model = (directory / 'policy.onnx').read_bytes()
        if hashlib.sha256(model).hexdigest() != self.manifest['sha256']:
            raise ValueError('ONNX 文件校验不一致')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(model, sess_options=options, providers=['CPUExecutionProvider'])

    def predict(self, states, images=None):
        if not isinstance(states, (list, np.ndarray)):
            raise ValueError(f'states 必须是 [batch,{self.state_dim}] 数值数组')
        if isinstance(states, list) and any(not isinstance(row, list) or any(type(value) not in (int, float) for value in row) for row in states):
            raise ValueError('states 只能包含数值，不能使用布尔值或字符串')
        array = np.asarray(states)
        if array.dtype.kind not in 'fiu' or array.ndim != 2 or array.shape[1] != self.state_dim or not 1 <= array.shape[0] <= 64:
            raise ValueError(f'states 必须是 [1–64,{self.state_dim}] 数值数组，不接受布尔值')
        array = array.astype(np.float32)
        if not np.isfinite(array).all():
            raise ValueError('states 不能包含非有限值')
        feed = {'state': array}
        if self.manifest.get('cameras'):
            if images is None:
                raise ValueError('视觉策略必须提供 images，格式 [batch,3,64,64]，数值范围 [0,1]')
            image = np.asarray(images)
            if image.dtype.kind not in 'fiu' or image.shape != (len(array), 3, 64, 64):
                raise ValueError('images 必须是 [batch,3,64,64] 数值数组')
            if not np.isfinite(image).all() or image.min() < 0 or image.max() > 1:
                raise ValueError('images 必须为 [0,1] 的有限 RGB 数值')
            feed['wrist'] = image.astype(np.float32)
        actions = self.session.run(['action'], feed)[0]
        if actions.shape != (len(array), 6) or not np.isfinite(actions).all() or np.max(np.abs(actions)) > 1.00001:
            raise ValueError('ONNX 输出动作无效')
        return np.clip(actions, -1, 1)

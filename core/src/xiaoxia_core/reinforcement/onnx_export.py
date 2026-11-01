"""导出确定性 SAC Actor 到 ONNX，并核对 CPU Runtime 与 PyTorch 输出一致性。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import hashlib
import json
from pathlib import Path

import numpy as np

from ..imitation.api_jobs import atomic_json
from ..safety import JOINTS


class BallOnnxExporter:
    def export(self, checkpoint: Path, directory: Path, *, policy=None):
        import onnx
        import onnxruntime as ort
        import torch
        from .learning import make_policy

        class DeterministicActor(torch.nn.Module):
            def __init__(self, actor):
                super().__init__()
                self.actor = actor

            def forward(self, state):
                features = self.actor.encoder({'observation.state': state})
                return torch.tanh(self.actor.mean_layer(self.actor.network(features)))

        if policy is None:
            policy = make_policy({'cameras': [], 'state_dim': 18}, 'cpu')
            policy.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True))
        # 使用独立 CPU 副本，不改变训练器的设备或权重。
        from copy import deepcopy
        model = DeterministicActor(deepcopy(policy.actor).cpu().eval()).eval()
        temporary = directory / 'policy.exporting.onnx'
        path = directory / 'policy.onnx'
        try:
            with torch.inference_mode():
                torch.onnx.export(model, (torch.zeros(1, 18),), str(temporary), dynamo=False,
                    opset_version=17, input_names=['state'], output_names=['action'],
                    dynamic_axes={'state': {0: 'batch'}, 'action': {0: 'batch'}})
            data = temporary.read_bytes()
            onnx.checker.check_model(onnx.load_model_from_string(data))
            session = ort.InferenceSession(data, providers=['CPUExecutionProvider'])
            sample = np.random.default_rng(42).normal(size=(4, 18)).astype(np.float32)
            sample[0] = 0
            with torch.inference_mode():
                expected = model(torch.from_numpy(sample)).numpy()
            actual = session.run(['action'], {'state': sample})[0]
            error = float(np.max(np.abs(expected - actual)))
            if not np.allclose(expected, actual, rtol=1e-4, atol=1e-5):
                raise ValueError(f'ONNX 与 PyTorch 输出不一致，最大绝对误差 {error}')
            manifest = {'task': 'ball_pickup', 'format': 'onnx', 'opset': 17, 'state_dim': 18,
                'input': {'name': 'state', 'dtype': 'float32', 'shape': ['batch', 18]},
                'output': {'name': 'action', 'dtype': 'float32', 'shape': ['batch', 6]},
                'joint_order': list(JOINTS), 'state_order': 'joint_positions_6,joint_velocities_6,ball_xyz_3,ball_minus_tip_xyz_3',
                'action_space': 'normalized_joint_delta', 'action_scale_rad': .08,
                'deterministic': True, 'action_formula': 'tanh(actor_mean)', 'physical': False,
                'sha256': hashlib.sha256(data).hexdigest(), 'checkpoint': checkpoint.name,
                'max_absolute_error': error, 'provider': 'CPUExecutionProvider'}
            temporary.replace(path)
            atomic_json(directory / 'policy.onnx.json', manifest)
            return {'onnx': str(path), 'manifest': str(directory / 'policy.onnx.json'),
                    'max_absolute_error': error, 'sha256': manifest['sha256']}
        finally:
            temporary.unlink(missing_ok=True)

    def from_directory(self, source: Path, destination: Path):
        config = json.loads((source / 'policy_config.json').read_text(encoding='utf-8'))
        if config.get('task') != 'ball_pickup' or config.get('state_dim') != 18:
            raise ValueError('只支持当前抓球任务的 18 维策略')
        weights = json.loads((source / 'weights.json').read_text(encoding='utf-8'))
        checkpoint = source / weights['file']
        if not checkpoint.resolve().is_relative_to(source.resolve()):
            raise ValueError('策略权重路径超出任务目录')
        return self.export(checkpoint, destination)

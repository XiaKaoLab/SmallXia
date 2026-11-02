"""保存实机到显示模型的腕部旋转偏移，独立于电机行程校准与夹爪开合。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from hashlib import sha256
import json
from math import isfinite, pi, radians
from pathlib import Path
import re

from ..imitation.api_jobs import atomic_json


class DisplayFrame:
    root = Path(__file__).resolve().parents[3] / 'data/display_frames'

    @staticmethod
    def fingerprint(calibration):
        return sha256(json.dumps(calibration, sort_keys=True).encode()).hexdigest()

    @classmethod
    def path(cls, port):
        if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
            raise ValueError('请选择 COM 口')
        return cls.root / f'{port}-so100.json'

    @classmethod
    def save(cls, port, calibration, degrees):
        if isinstance(degrees, bool) or not isinstance(degrees, (int, float)) or not isfinite(degrees) or not -180 <= degrees <= 180:
            raise ValueError('旋转偏移须在 -180° 到 180° 之间')
        cls.root.mkdir(parents=True, exist_ok=True)
        config = {'port': port, 'model': 'so100_mid_calib', 'calibration_sha256': cls.fingerprint(calibration),
                  'wrist_roll_offset_deg': degrees, 'display_only': True}
        atomic_json(cls.path(port), config)
        return config

    @classmethod
    def load(cls, port, calibration):
        path = cls.path(port)
        if not path.exists():
            return 0.0
        config = json.loads(path.read_text(encoding='utf-8'))
        if config.get('port') != port or config.get('model') != 'so100_mid_calib' or config.get('calibration_sha256') != cls.fingerprint(calibration):
            return 0.0  # 新校准或其他设备不会继承旧姿态修正。
        value = config['wrist_roll_offset_deg']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not -180 <= value <= 180:
            raise ValueError('旋转对齐配置无效')
        return float(value)

    @staticmethod
    def apply(angles, degrees):
        result = dict(angles)
        # 全周腕轴的等价显示角，不改动其他五轴或电机计数。
        value = result['wrist_roll'] + radians(degrees)
        result['wrist_roll'] = (value + pi) % (2 * pi) - pi if degrees else value
        return result

"""发布各独立仿真环境的轻量预览，通过持久桌面流读取真实训练状态。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
from pathlib import Path
from time import monotonic, sleep, time_ns

from ..imitation.api_jobs import atomic_json


class TrainingPreviewPublisher:
    def __init__(self, directory):
        self.directory = directory
        self.last_publish = 0

    def publish(self, environments, *, force=False):
        if not force and monotonic() - self.last_publish < .08:
            return
        atomic_json(self.directory / 'preview.json', {'job_id': self.directory.name,
            'timestamp_ns': time_ns(), 'physical': False,
            'snapshots': [{**env.snapshot(), 'env_index': index} for index, env in enumerate(environments)]})
        self.last_publish = monotonic()


class TrainingPreviewStream:
    def __init__(self, root: Path):
        self.root = root

    def run(self, emit):
        deadline, scan_at = monotonic() + 300, 0
        selected, last_version = None, None
        while monotonic() < deadline:
            if monotonic() >= scan_at:
                candidates = []
                for path in self.root.glob('*/status.json'):
                    try:
                        state = json.loads(path.read_text(encoding='utf-8'))
                        if state['kind'] in ('ball_pickup', 'ball_onnx_rollout') and state['status'] in ('queued', 'running'):
                            candidates.append((state.get('created_at_ns', 0), path.parent))
                    except (OSError, ValueError, KeyError):
                        continue
                if candidates:
                    selected = max(candidates, key=lambda item: item[0])[1]
                scan_at = monotonic() + 1
            if selected:
                path = selected / 'preview.json'
                try:
                    version = (selected.name, path.stat().st_mtime_ns)
                    if version != last_version:
                        preview = json.loads(path.read_text(encoding='utf-8'))
                        emit({'type': 'preview', 'data': preview})
                        last_version = version
                except (OSError, ValueError):
                    pass  # 原子替换期间保留上一帧，下次读取；不复制或伪造其他环境。
            sleep(.08)
        emit({'type': 'completed'})

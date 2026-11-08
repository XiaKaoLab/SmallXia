"""功能：下载固定版本 gesture-commands，保留来源并提取80段相对动作。
Created on 2026-11-08; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
import numpy as np
import pandas as pd


class GestureImporter:
    revision = 'e253be78317eedcf221987653253de2a0e42701e'
    repo = 'satyadevineni/gesture-commands'
    names = {'wave': '挥手', 'spin': '旋转', 'bow': '鞠躬', 'False': '未命名动作（原标签 False）'}

    def run(self):
        root = Path(__file__).resolve().parents[1] / 'data/gesture_library'
        source = root / 'source'; source.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for name in ('README.md', 'meta/info.json', 'meta/tasks.parquet', 'data/chunk-000/file-000.parquet'):
            data = urlopen(f'https://huggingface.co/datasets/{self.repo}/resolve/{self.revision}/{name}', timeout=60).read()
            path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        rows = pd.read_parquet(source / 'data/chunk-000/file-000.parquet')
        tasks = pd.read_parquet(source / 'meta/tasks.parquet').reset_index()
        catalog = {'source': f'https://huggingface.co/datasets/{self.repo}', 'revision': self.revision,
                   'license': 'apache-2.0', 'sha256': hashes, 'representation': 'relative_shape_normalized',
                   'note': '原始角度单位与校准未确认；只使用相对变化形状，不回放源绝对位置。', 'actions': []}
        for _, task in tasks.iterrows():
            label = str(task['task']); key = label.lower() if label != 'False' else 'unlabeled'
            selected = rows[rows.task_index == task.task_index]
            episodes = []
            for episode_id, episode in selected.groupby('episode_index'):
                episode = episode.sort_values('frame_index')
                raw = np.stack(episode.action).astype(float)
                if not np.isfinite(raw).all(): raise ValueError('源动作包含非有限值')
                delta = raw - raw[0]; extent = np.max(np.abs(delta), axis=0)
                # 小于2个源数值单位的变化按静止处理，避免把微小噪声放大成动作。
                normalized = np.divide(delta, extent, out=np.zeros_like(delta), where=extent >= 2)
                indices = list(range(0, len(episode), 9))
                if indices[-1] != len(episode)-1: indices.append(len(episode)-1)
                timestamps = episode.timestamp.to_numpy(); timestamps = timestamps-timestamps[0]
                episodes.append({'episode': int(episode_id), 'duration': float(timestamps[-1]),
                    'frames': [{'t': round(float(timestamps[i]), 4), 'pose': normalized[i].round(5).tolist()} for i in indices]})
            item = {'id': key, 'name': self.names.get(label, label), 'source_label': label, 'variants': len(episodes)}
            catalog['actions'].append(item)
            (root / f'{key}.json').write_text(json.dumps({'metadata': item, 'episodes': episodes}, ensure_ascii=False), encoding='utf8')
        (root / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({'directory': str(root), 'actions': catalog['actions']}, ensure_ascii=False))


if __name__ == '__main__': GestureImporter().run()

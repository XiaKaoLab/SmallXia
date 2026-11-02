"""从官方 SO100 一体式 STL 提取显示用支架，避免翻转支架时改变固定夹爪。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from hashlib import sha256
import json
from pathlib import Path

import trimesh


class SO100CameraSupportBuilder:
    def build(self, directory: Path):
        source = directory / 'wrist_camera_mount_so100.stl'
        mesh = trimesh.load(source, force='mesh')
        # 原夹爪主体的 CAD Y 范围为 ±24 mm；只保留向外延伸的支架。
        support = mesh.slice_plane(plane_origin=[0, 24, 0], plane_normal=[0, 1, 0], cap=False)
        destination = directory / 'camera_support_so100.stl'
        support.export(destination)
        path = directory / 'provenance.json'
        provenance = json.loads(path.read_text(encoding='utf-8'))
        provenance['display_support'] = {
            'file': destination.name, 'source_sha256': sha256(source.read_bytes()).hexdigest(),
            'sha256': sha256(destination.read_bytes()).hexdigest(), 'clip_plane_cad_mm': 'Y >= 24',
            'rotation_matrix': [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
            'translation_m': [0, -.001, 0], 'scale': .001,
            'note': 'Display-only open cut mesh. Opposite mounting side; original fixed jaw stays unchanged. Not a printable replacement.',
        }
        path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    SO100CameraSupportBuilder().build(Path(__file__).resolve().parents[2] / 'table/public/robots/so100/camera')

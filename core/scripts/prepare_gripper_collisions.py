"""离线从原始手指 STL 生成 CoACD 凸碰撞分解，不改变视觉模型。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from hashlib import sha256
import json
from pathlib import Path


class GripperCollisionBuilder:
    def build(self, assets: Path):
        import coacd
        import trimesh
        for name in ('wrist_roll_follower_so101_v1', 'moving_jaw_so101_v1'):
            source = assets / f'{name}.stl'
            mesh = trimesh.load(source, force='mesh')
            parts = coacd.run_coacd(coacd.Mesh(mesh.vertices, mesh.faces), threshold=.03, resolution=2000,
                mcts_iterations=60, mcts_max_depth=4, merge=True, max_convex_hull=24, seed=42)
            directory = assets / 'collision' / name
            directory.mkdir(parents=True, exist_ok=True)
            for index, (vertices, faces) in enumerate(parts):
                trimesh.Trimesh(vertices, faces, process=False).export(directory / f'{index:02d}.obj')
            metadata = {'source': source.name, 'source_sha256': sha256(source.read_bytes()).hexdigest(),
                'method': 'CoACD', 'coacd_version': '1.0.14', 'threshold': .03, 'resolution': 2000,
                'mcts_iterations': 60, 'mcts_max_depth': 4, 'max_convex_hull': 24, 'seed': 42, 'parts': len(parts)}
            (directory / 'source.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')


if __name__ == '__main__':
    GripperCollisionBuilder().build(Path(__file__).resolve().parents[2] / 'table/public/robots/so101/assets')

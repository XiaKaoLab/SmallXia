"""用源 STL 的凸分解保留夹爪凹槽，只替换仿真碰撞网格。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


class GripperCollisionGeometry:
    parts = {'wrist_roll_follower_so101_v1', 'moving_jaw_so101_v1'}

    def apply(self, root, urdf: Path):
        for link in root.findall('link'):
            for collision in list(link.findall('collision')):
                mesh = collision.find('geometry/mesh')
                if mesh is None or Path(mesh.attrib['filename']).stem not in self.parts:
                    continue
                name = Path(mesh.attrib['filename']).stem
                directory = urdf.parent / 'assets/collision' / name
                metadata = json.loads((directory / 'source.json').read_text(encoding='utf-8'))
                source_hash = metadata.get('source_sha256')
                if source_hash and sha256((urdf.parent / mesh.attrib['filename']).read_bytes()).hexdigest() != source_hash:
                    raise ValueError('源手指 STL 已更新，请重新生成凸碰撞分解')
                if type(metadata.get('parts')) is not int or not 1 <= metadata['parts'] <= 64:
                    raise ValueError('手指碰撞分解数量无效')
                for index in range(metadata['parts']):
                    path = directory / f'{index:02d}.obj'
                    if not path.is_file():
                        raise ValueError(f'缺少手指碰撞分解：{path.name}')
                    part = deepcopy(collision)
                    part.find('geometry/mesh').set('filename', path.relative_to(urdf.parent).as_posix())
                    link.append(part)
                link.remove(collision)

"""将官方 SO-100 重参数化为行程中点零位，保留原始几何与可达姿态。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation


class SO100ModelAdapter:
    links = {'base': 'base_link', 'shoulder': 'shoulder_link', 'upper_arm': 'upper_arm_link',
             'lower_arm': 'lower_arm_link', 'wrist': 'wrist_link', 'gripper': 'gripper_link', 'jaw': 'jaw_link'}

    def convert(self, source: Path, destination: Path):
        root = ET.parse(source).getroot()
        root.set('name', 'so100_mid_calib')
        for link in root.findall('link'):
            link.set('name', self.links[link.attrib['name']])
        for joint in root.findall('joint'):
            for field in ('parent', 'child'):
                node = joint.find(field)
                node.set('link', self.links[node.attrib['link']])
            limit, origin, axis = joint.find('limit'), joint.find('origin'), joint.find('axis')
            # 夹爪仍以闭合为零，其余五轴改为行程中点；不缩放角度。
            offset = 0 if joint.attrib['name'] == 'gripper' else (float(limit.attrib['lower']) + float(limit.attrib['upper'])) / 2
            rotation = Rotation.from_euler('xyz', [float(v) for v in origin.attrib.get('rpy', '0 0 0').split()])
            rotation *= Rotation.from_rotvec(np.array([float(v) for v in axis.attrib['xyz'].split()]) * offset)
            origin.set('rpy', ' '.join(f'{v:.12g}' for v in rotation.as_euler('xyz')))
            for key in ('lower', 'upper'):
                limit.set(key, f'{float(limit.attrib[key]) - offset:.12g}')
        ET.indent(root)
        ET.ElementTree(root).write(destination, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    directory = Path(__file__).resolve().parents[2] / 'table/public/robots/so100'
    SO100ModelAdapter().convert(directory / 'so100.urdf', directory / 'so100_mid_calib.urdf')

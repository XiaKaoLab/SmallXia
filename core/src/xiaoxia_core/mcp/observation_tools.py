"""多视角定时截图与同期关节CSV，提供真实视觉输入。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import base64
import csv
import json
from datetime import datetime, timezone
from ..communication.camera_calibration import CameraCalibration
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4
from mcp.types import ImageContent, TextContent
from .blocks_tools import BlocksTools

class ObservationTools:
    def robot_list_cameras(self) -> dict:
        """列出当前真实摄像头及虚拟腕部相机的来源、设备ID和名称。设备被发现不代表读取成功，不推断其安装位置或所属机械臂。"""
        return CameraCalibration.camera_request('')

    def robot_observe(self, samples: int = 2, interval_s: float = 0.5, views: list[str] | None = None, source: str = "simulation", camera_id: str | None = None) -> list[TextContent | ImageContent]:
        """只读截图及CSV。source=simulation为多视角渲染，real为真实摄像头。真实相机先robot_list_cameras，再指定其中source=real的camera_id，不猜设备，不默认为第一个；real不接受front/side/top视角。每图明确设备身份和时间；真实相机不包含关节反馈、不证明相机安装于指定机械臂。1–3次，间隔0–2秒。"""
        if source not in ('simulation', 'real'):
            raise ValueError('来源仅支持simulation或real')
        device = None
        if source == 'real':
            if views is not None:
                raise ValueError('真实相机不支持切换虚拟视角，请省略views')
            devices = self.robot_list_cameras()['cameras']
            device = next((item for item in devices if item['id'] == camera_id and item.get('source') == 'real'), None)
            if device is None:
                raise ValueError('请选择相机列表中真实摄像头的camera_id')
        elif camera_id is not None:
            raise ValueError('仿真观察不接受真实相机ID')
        views = ['front', 'side', 'top'] if views is None else views
        if type(samples) is not int or not 1 <= samples <= 3 or not 0 <= interval_s <= 2:
            raise ValueError('次数1–3，间隔0–2秒')
        if not views or len(views) > 3 or len(set(views)) != len(views) or any(v not in ('front', 'side', 'top') for v in views):
            raise ValueError('视角应为front、side、top，不重复')
        folder = Path(__file__).resolve().parents[3] / 'data' / 'observations' / uuid4().hex
        folder.mkdir(parents=True)
        rows, content, frames = [], [], []
        deadline = monotonic() + 15
        for sample in range(samples):
            if sample: sleep(interval_s)
            if device:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError('相机采样超时，未返回完整观察结果')
                captured = CameraCalibration.camera_request('/' + device['id'] + '/frame', timeout=min(8, remaining))
                if captured.get('source') != 'real' or captured.get('physical') is not True or captured.get('camera_id') != device['id']:
                    raise ValueError('相机回执来源或设备身份不匹配，已拒绝图像')
                if captured.get('encoding') != 'jpeg' or not 0 <= captured.get('age_ms', -1) <= 2000:
                    raise ValueError('真实相机格式无效或画面已过期')
                identity = dict(source_kind='real_camera', camera_id=device['id'], camera_name=device['name'],
                                physical=True, timestamp_ns=captured['timestamp_ns'],
                                timestamp_basis=captured['timestamp_basis'], sequence=captured['sequence'],
                                age_ms=captured['age_ms'], robot_association='unverified')
                frame = dict(timestamp=datetime.fromtimestamp(captured['timestamp_ns'] / 1e9, timezone.utc).isoformat(),
                             source='real_camera', joints={}, identity=identity,
                             images=[dict(view='camera', data_url='data:image/jpeg;base64,' + captured['image_base64'])])
            else:
                frame = BlocksTools().execute('observe', {'views': views})['result']
                frame['identity'] = dict(source_kind=frame['source'], camera_id=None, camera_name='仿真观察视角',
                                         physical=False, timestamp_basis='webview_render_capture',
                                         robot_association='mapped_render' if frame['source'] == 'hardware_mapped_render' else 'simulation')
            for image in frame.pop('images'):
                raw = base64.b64decode(image['data_url'].split(',', 1)[1], validate=True)
                mime = 'image/jpeg' if device else 'image/png'
                signature = bytes([255,216,255]) if device else bytes([137,80,78,71,13,10,26,10])
                if len(raw) > 2_000_000 or not raw.startswith(signature):
                    raise ValueError('截图格式或大小无效')
                filename = f"{sample + 1:02d}-{image['view']}." + ("jpg" if device else "png")
                (folder / filename).write_bytes(raw)
                rows.append(dict(sample=sample + 1, timestamp=frame['timestamp'], source=frame['source'], view=image['view'], image=filename, unit='' if device else 'rad', **frame['identity'], **frame['joints']))
                content.extend([TextContent(type='text', text=json.dumps(dict(sample=sample + 1, timestamp=frame['timestamp'], view=image['view'], image=filename, **frame['identity']), ensure_ascii=False)), ImageContent(type='image', mimeType=mime, data=base64.b64encode(raw).decode())])
            frames.append(frame)
        csv_path = folder / 'observations.csv'
        with csv_path.open('w', newline='', encoding='utf-8-sig') as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        manifest = {'directory': str(folder), 'csv': str(csv_path), 'frames': frames, 'physical': source == 'real',
                    'note': '图像身份以每帧identity为准。真实相机仅提供图像，无关节反馈；接收时间不等于曝光时间。仿真/映射渲染不是真实相机。'}
        (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        content.insert(0, TextContent(type='text', text=json.dumps({**manifest, 'csv_content': csv_path.read_text(encoding='utf-8-sig')}, ensure_ascii=False)))
        return content

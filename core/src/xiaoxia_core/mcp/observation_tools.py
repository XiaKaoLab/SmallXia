"""多视角定时截图与同期关节CSV，提供真实视觉输入。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import base64
import csv
import json
from pathlib import Path
from time import sleep
from uuid import uuid4
from mcp.types import ImageContent, TextContent
from .blocks_tools import BlocksTools

class ObservationTools:
    def robot_observe(self, samples: int = 2, interval_s: float = 0.5, views: list[str] | None = None) -> list[TextContent | ImageContent]:
        """只读观察机械臂：1–3次采样，间隔0–2秒，视角front/side/top。保存PNG和同期渲染角度CSV(rad)。不启动动作，可在程序运行时使用。仿真截图不是真实相机，真机映射仅是渲染反馈；训练观察第一个环境。"""
        views = ['front', 'side', 'top'] if views is None else views
        if type(samples) is not int or not 1 <= samples <= 3 or not 0 <= interval_s <= 2:
            raise ValueError('次数1–3，间隔0–2秒')
        if not views or len(views) > 3 or len(set(views)) != len(views) or any(v not in ('front', 'side', 'top') for v in views):
            raise ValueError('视角应为front、side、top，不重复')
        folder = Path(__file__).resolve().parents[3] / 'data' / 'observations' / uuid4().hex
        folder.mkdir(parents=True)
        rows, content, frames = [], [], []
        for sample in range(samples):
            if sample: sleep(interval_s)
            frame = BlocksTools().execute('observe', {'views': views})['result']
            for image in frame.pop('images'):
                raw = base64.b64decode(image['data_url'].split(',', 1)[1], validate=True)
                if len(raw) > 2_000_000 or not raw.startswith(bytes([137,80,78,71,13,10,26,10])):
                    raise ValueError('截图格式或大小无效')
                filename = f"{sample + 1:02d}-{image['view']}.png"
                (folder / filename).write_bytes(raw)
                rows.append(dict(sample=sample + 1, timestamp=frame['timestamp'], source=frame['source'], view=image['view'], image=filename, unit='rad', **frame['joints']))
                content.extend([TextContent(type='text', text=f"采样{sample + 1}，{frame['timestamp']}，{image['view']}，{frame['source']}"), ImageContent(type='image', mimeType='image/png', data=base64.b64encode(raw).decode())])
            frames.append(frame)
        csv_path = folder / 'observations.csv'
        with csv_path.open('w', newline='', encoding='utf-8-sig') as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        manifest = {'directory': str(folder), 'csv': str(csv_path), 'frames': frames, 'physical': False,
                    'note': '同一采样共用时间与姿态，间隔以CSV时间为准；渲染角度不是真机编码器反馈。'}
        (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        content.insert(0, TextContent(type='text', text=json.dumps({**manifest, 'csv_content': csv_path.read_text(encoding='utf-8-sig')}, ensure_ascii=False)))
        return content

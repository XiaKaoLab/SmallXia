"""真实相机棋盘格内参标定：持久采样、角点检查、误差报告和参数导出。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import base64
from contextlib import contextmanager
import json
from math import isfinite
import os
from pathlib import Path
import re
import sqlite3
from time import sleep, time
from urllib.request import Request, urlopen
from uuid import uuid4

from ..imitation.api_jobs import atomic_json, identifier


class CameraCalibration:
    root = Path(__file__).resolve().parents[3] / 'data/camera_calibration'
    minimum_samples = 12

    def __init__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with self.database() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, config TEXT, result TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS samples (id TEXT PRIMARY KEY, session TEXT, corners TEXT, width INTEGER, height INTEGER, timestamp REAL)')

    @contextmanager
    def database(self):
        connection = sqlite3.connect(self.root / 'sessions.sqlite3', timeout=3)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def camera_request(path):
        request = Request('http://127.0.0.1:8766/api/v1/cameras' + path,
                          headers={'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        with urlopen(request, timeout=4) as response:
            return json.load(response)

    def start(self, camera_id, columns=9, rows=6, square_mm=25):
        if not isinstance(camera_id, str) or not re.fullmatch('opencv_[0-9a-f]{16}', camera_id):
            raise ValueError('内参标定必须选择发现的真实相机，不接受虚拟画面')
        if type(columns) is not int or type(rows) is not int or not 3 <= columns <= 20 or not 3 <= rows <= 20:
            raise ValueError('棋盘格内角点的列、行数须为 3 到 20 的整数')
        if isinstance(square_mm, bool) or not isinstance(square_mm, (int, float)) or not isfinite(square_mm) or not 1 <= square_mm <= 200:
            raise ValueError('实际方格边长须在 1 到 200 mm 之间')
        camera = next((item for item in self.camera_request('')['cameras']
                       if item['id'] == camera_id and item.get('physical') is True), None)
        if camera is None:
            raise ValueError('真实相机未找到，请刷新相机列表')
        identity = uuid4().hex
        config = {'camera_id': camera_id, 'camera_name': camera['name'], 'columns': columns,
                  'rows': rows, 'square_mm': square_mm, 'created_at': time(), 'physical': True}
        with self.database() as db:
            db.execute('INSERT INTO sessions VALUES (?, ?, NULL)', (identity, json.dumps(config)))
        (self.root / identity).mkdir()
        return self.get(identity)

    def get(self, session_id):
        identity = identifier(session_id)
        with self.database() as db:
            row = db.execute('SELECT config,result FROM sessions WHERE id=?', (identity,)).fetchone()
            if row is None:
                raise ValueError('相机标定会话不存在')
            count = db.execute('SELECT COUNT(*) FROM samples WHERE session=?', (identity,)).fetchone()[0]
        return {'id': identity, **json.loads(row[0]), 'samples': count, 'minimum_samples': self.minimum_samples,
                'result': json.loads(row[1]) if row[1] else None}

    def detect(self, session_id):
        import cv2
        import numpy as np
        state = self.get(session_id)
        frame = self.camera_request('/' + state['camera_id'] + '/frame')
        if frame.get('source') != 'real' or frame.get('camera_id') != state['camera_id']:
            raise ValueError('返回帧的真实相机身份不匹配')
        raw = base64.b64decode(frame['image_base64'], validate=True)
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('真实相机图像解码失败')
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCornersSB(gray, (state['columns'], state['rows']),
            flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
        return state, image, raw, corners if found else None

    def preview(self, session_id):
        import cv2
        state, image, _, corners = self.detect(session_id)
        if corners is not None:
            cv2.drawChessboardCorners(image, (state['columns'], state['rows']), corners, True)
        if state['result']:
            import numpy as np
            result = state['result']
            if result['image_size'] == [image.shape[1], image.shape[0]]:
                image = cv2.undistort(image, np.asarray(result['camera_matrix']), np.asarray(result['distortion']))
        ok, encoded = cv2.imencode('.jpg', image)
        if not ok:
            raise ValueError('标定预览编码失败')
        return {**state, 'board_found': corners is not None,
                'image': 'data:image/jpeg;base64,' + base64.b64encode(encoded).decode('ascii')}

    def capture(self, session_id):
        import numpy as np
        import cv2
        state, image, raw, corners = self.detect(session_id)
        if corners is None:
            raise ValueError('未识别到完整棋盘格，请检查内角点行列数、清晰度及遮挡')
        height, width = image.shape[:2]
        points = corners.reshape(-1, 2)
        if cv2.contourArea(cv2.convexHull(points)) < width * height * .02:
            raise ValueError('标定板太小，请靠近相机')
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT corners,width,height FROM samples WHERE session=?', (state['id'],)).fetchall()
            if len(existing) >= 80:
                raise ValueError('已采集 80 帧，请计算标定或新建会话')
            for saved, w, h in existing:
                if (width, height) != (w, h):
                    raise ValueError('采样分辨率发生变化，请重新建立标定会话')
                previous = np.asarray(json.loads(saved)).reshape(-1, 2)
                distance = min(np.linalg.norm(points - previous, axis=1).mean(),
                               np.linalg.norm(points - previous[::-1], axis=1).mean())
                if distance < 10:
                    raise ValueError('与已有样本过于相似，请移动或倾斜标定板后再采集')
            sample_id = uuid4().hex
            (self.root / state['id'] / (sample_id + '.jpg')).write_bytes(raw)
            db.execute('INSERT INTO samples VALUES (?,?,?,?,?,?)',
                (sample_id, state['id'], json.dumps(corners.tolist()), width, height, time()))
            db.execute('UPDATE sessions SET result=NULL WHERE id=?', (state['id'],))
            # 增加样本后旧结果不再作为当前标定结果。
            (self.root / state['id'] / 'intrinsics.json').unlink(missing_ok=True)
        return self.get(state['id'])

    @staticmethod
    def solve_points(config, image_points, image_size):
        import cv2
        import numpy as np
        if len(image_points) < CameraCalibration.minimum_samples:
            raise ValueError('至少需要 12 帧有效图像，建议采集 20 帧以上不同距离和倾角的图像')
        objects = np.zeros((config['columns'] * config['rows'], 3), np.float32)
        objects[:, :2] = np.mgrid[:config['columns'], :config['rows']].T.reshape(-1, 2) * config['square_mm'] / 1000
        points = [np.asarray(item, dtype=np.float32).reshape(-1, 1, 2) for item in image_points]
        rms, matrix, distortion, rotations, translations = cv2.calibrateCamera(
            [objects.copy() for _ in points], points, tuple(image_size), None, None)
        if not np.isfinite(matrix).all() or not np.isfinite(distortion).all() or not isfinite(rms) or min(matrix[0, 0], matrix[1, 1]) <= 0:
            raise ValueError('标定解无效，请增加不同倾角、位置和距离的有效样本')
        errors = []
        for observed, rotation, translation in zip(points, rotations, translations):
            projected, _ = cv2.projectPoints(objects, rotation, translation, matrix, distortion)
            errors.append(float(np.sqrt(np.mean(np.sum((observed - projected) ** 2, axis=2)))))
        centers = np.asarray([item.reshape(-1, 2).mean(axis=0) for item in points])
        bins = {(min(3, int(x / image_size[0] * 4)), min(2, int(y / image_size[1] * 3))) for x, y in centers}
        normals = np.asarray([cv2.Rodrigues(rotation)[0][:, 2] for rotation in rotations])
        tilt_span = float(np.degrees(np.arccos(np.clip(normals @ normals.T, -1, 1))).max())
        warnings = []
        if rms > 1.0: warnings.append('RMS 重投影误差超过 1 像素，请检查模糊图像、板面平整度和角点检测')
        if len(bins) < 4: warnings.append('标定板覆盖区域不足，请补充画面边缘和不同位置')
        if tilt_span < 10: warnings.append('标定板倾角变化不足，请补充不同方向的倾斜视角')
        if not 0 <= matrix[0, 2] < image_size[0] or not 0 <= matrix[1, 2] < image_size[1]:
            warnings.append('主点位于画面外，请重新检查采样与棋盘格设置')
        return {'model': 'opencv_pinhole_brown_conrady', 'camera_matrix': matrix.tolist(),
                'distortion': distortion.reshape(-1).tolist(), 'distortion_order': ['k1', 'k2', 'p1', 'p2', 'k3'],
                'image_size': list(image_size), 'rms_px': float(rms), 'per_view_rms_px': errors,
                'samples': len(points), 'coverage_bins': len(bins), 'tilt_span_deg': tilt_span,
                'warnings': warnings, 'quality': 'needs_review' if warnings else 'passed_checks',
                'independent_validation_passed': False, 'calibrated_at': time()}

    def solve(self, session_id):
        state = self.get(session_id)
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute('SELECT corners,width,height FROM samples WHERE session=? ORDER BY timestamp', (state['id'],)).fetchall()
            if not rows:
                raise ValueError('尚未采集标定图像')
            result = self.solve_points(state, [json.loads(row[0]) for row in rows], (rows[0][1], rows[0][2]))
            result.update(camera_id=state['camera_id'], camera_name=state['camera_name'],
                          board={'columns': state['columns'], 'rows': state['rows'], 'square_mm': state['square_mm']})
            atomic_json(self.root / state['id'] / 'intrinsics.json', result)
            db.execute('UPDATE sessions SET result=? WHERE id=?', (json.dumps(result), state['id']))
        return self.get(state['id'])

    def stream(self, session_id, emit):
        while True:
            try:
                emit({'type': 'calibration', 'data': self.preview(session_id)})
            except (ValueError, OSError, RuntimeError) as error:
                emit({'type': 'calibration', 'data': {**self.get(session_id), 'error': str(error)}})
            sleep(.3)

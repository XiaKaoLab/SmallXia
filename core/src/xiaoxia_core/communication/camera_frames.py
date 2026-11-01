"""统一虚拟渲染帧和本机真实相机帧，显式区分来源与新鲜度。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import base64
from io import BytesIO
from threading import RLock
from time import monotonic, time_ns
from PIL import Image
from .camera_discovery import CameraDiscovery


class CameraFrames:
    def __init__(self):
        self._lock = RLock()
        self._virtual = None
        self._received = 0.0
        self._capture = None
        self._device = None
        self._sequence = 0
        self.discovery = CameraDiscovery()

    def publish(self, body):
        raw = base64.b64decode(body['image_base64'], validate=True)
        if len(raw) > 1024 * 1024:
            raise ValueError('图像超过 1 MB')
        with Image.open(BytesIO(raw)) as image:
            if image.format != 'JPEG' or max(image.size) > 1920:
                raise ValueError('需要不超过 1920 像素的 JPEG')
            image.verify()
            width, height = image.size
        with self._lock:
            self._virtual = self._frame('virtual', raw, width, height)
            self._received = monotonic()
            return {key: value for key, value in self._virtual.items() if key != 'image_base64'}

    def configure_real(self, body):
        import cv2
        index = body.get('device_index', 0)
        if type(index) is not int or not 0 <= index <= 32 or type(body.get('enabled', True)) is not bool:
            raise ValueError('设备编号需为 0 到 32 的整数，enabled 需为布尔值')
        with self._lock:
            self.close()
            if not body.get('enabled', True):
                return {'source': 'real', 'connected': False}
            capture = cv2.VideoCapture(index)
            if not capture.isOpened():
                capture.release()
                raise ValueError('真实相机无法打开')
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._capture = capture
            self._device = None
            return {'source': 'real', 'connected': True, 'device_index': index}

    def _frame(self, source, raw, width, height):
        self._sequence += 1
        return {'source': source, 'physical': source == 'real', 'sequence': self._sequence,
                'timestamp_ns': time_ns(), 'timestamp_basis': 'core_receive_time',
                'width': width, 'height': height, 'encoding': 'jpeg',
                'image_base64': base64.b64encode(raw).decode('ascii')}

    def devices(self):
        devices = self.discovery.list()
        with self._lock:
            if self._virtual is not None and monotonic() - self._received <= 2:
                devices.insert(0, {'id': 'virtual', 'name': '腕部虚拟相机', 'source': 'virtual', 'physical': False})
        return {'cameras': devices}

    def read(self, source):
        with self._lock:
            if source == 'virtual':
                if self._virtual is None or monotonic() - self._received > 2:
                    raise ValueError('虚拟画面未就绪或已过期，请先装配相机并保持 table 打开')
                return {**self._virtual, 'age_ms': round((monotonic() - self._received) * 1000)}
            if source.startswith('opencv_'):
                device = self.discovery.resolve(source)
                if self._capture is None or self._device != device['id']:
                    import cv2
                    self.close()
                    capture = cv2.VideoCapture(device['device_index'], device['backend'])
                    if not capture.isOpened():
                        capture.release()
                        raise ValueError('所选摄像头无法打开，可能被其他应用占用')
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self._capture, self._device = capture, device['id']
            if not (source == 'real' or source.startswith('opencv_')) or self._capture is None:
                raise ValueError('真实相机未连接，请先配置设备')
            import cv2
            ok, image = self._capture.read()
            if not ok:
                raise ValueError('真实相机读取失败')
            ok, raw = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise ValueError('真实相机编码失败')
            return {**self._frame('real', raw.tobytes(), image.shape[1], image.shape[0]), 'camera_id': self._device, 'age_ms': 0}

    def close(self):
        with self._lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
                self._device = None

"""按操作系统设备名称枚举摄像头，保留稳定标识与 OpenCV 后端映射。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import hashlib
import os


class CameraDiscovery:
    def list(self):
        import cv2
        from cv2_enumerate_cameras import enumerate_cameras
        backend = cv2.CAP_MSMF if os.name == 'nt' else cv2.CAP_ANY
        devices = []
        for camera in enumerate_cameras(backend):
            identity = f'{camera.backend}:{camera.path or camera.index}'
            devices.append({'id': 'opencv_' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                            'name': camera.name or f'摄像头 {camera.index}', 'source': 'real',
                            'device_index': camera.index, 'backend': camera.backend, 'physical': True})
        return devices

    def resolve(self, camera_id):
        camera = next((item for item in self.list() if item['id'] == camera_id), None)
        if camera is None:
            raise ValueError('所选摄像头已断开或不可用，请刷新相机列表')
        return camera

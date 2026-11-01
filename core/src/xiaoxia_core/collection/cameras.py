"""为任意设备附加 OpenCV 相机观测，图像文件仅写入 core 数据目录。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import re
from pathlib import Path
from time import monotonic_ns

from ..communication import RobotTransport
from ..contracts import Action, Observation


class CameraTransport(RobotTransport):
    def __init__(self, transport: RobotTransport, cameras: dict[str, int], directory: Path, width: int = 640, height: int = 480) -> None:
        if not all(re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in cameras) or min(width, height) < 1:
            raise ValueError("相机名称和分辨率无效")
        self.transport, self.cameras, self.directory = transport, cameras, directory
        self.width, self.height = width, height
        self._captures: dict = {}
        self.port = getattr(transport, "port", None)

    def connect(self) -> None:
        import cv2
        self.transport.connect()
        try:
            for name, index in self.cameras.items():
                capture = cv2.VideoCapture(index)
                self._captures[name] = capture
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                if not capture.isOpened():
                    raise RuntimeError(f"无法打开相机: {name}")
        except BaseException:
            self.disconnect()
            raise

    def read_observation(self) -> Observation:
        import cv2
        observation = self.transport.read_observation()
        paths = {}
        self.directory.mkdir(parents=True, exist_ok=True)
        for name, capture in self._captures.items():
            ok, frame = capture.read()
            if not ok or frame.shape[:2] != (self.height, self.width):
                raise RuntimeError(f"相机帧缺失或分辨率不符: {name}")
            path = self.directory / f"{name}-{monotonic_ns()}.png"
            # imencode + tofile 支持 Windows 中文路径。
            encoded, pixels = cv2.imencode(".png", frame)
            if not encoded:
                raise RuntimeError("相机图像编码失败")
            pixels.tofile(path)
            paths[name] = str(path)
        return Observation(observation.timestamp_ns, observation.joint_positions, paths)

    def send_action(self, action: Action) -> None:
        self.transport.send_action(action)

    @property
    def applied_action(self) -> Action:
        return self.transport.applied_action

    def disconnect(self) -> None:
        for capture in self._captures.values():
            capture.release()
        self._captures.clear()
        self.transport.disconnect()

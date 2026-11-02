"""从画面变量检测红色圆形候选，返回像素与归一化坐标；不推断深度或抓取成功。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from math import pi

from .frame_client import CameraFrameClient


class RedBallDetector:
    def detect(self, frame):
        import cv2
        import numpy as np
        rgb = CameraFrameClient.rgb(frame)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, (0, 100, 60), (10, 255, 255)) | cv2.inRange(hsv, (170, 100, 60), (179, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if area >= 20 and perimeter and 4 * pi * area / perimeter ** 2 >= .45:
                candidates.append((area, contour))
        result = {'found': False, 'x': None, 'y': None, 'normalized_x': None, 'normalized_y': None,
                  'radius': 0., 'area': 0., 'sequence': frame.get('sequence')}
        if candidates:
            area, contour = max(candidates, key=lambda item: item[0])
            (x, y), radius = cv2.minEnclosingCircle(contour)
            result.update(found=True, x=x, y=y, normalized_x=x / rgb.shape[1], normalized_y=y / rgb.shape[0],
                          radius=radius, area=area)
        return result

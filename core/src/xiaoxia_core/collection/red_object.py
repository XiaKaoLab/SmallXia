"""功能：识别任意形状的红色区域，以空间连续性保持目标身份。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from math import hypot
from .frame_client import CameraFrameClient


class RedObjectDetector:
    def __init__(self):
        self.previous = None
        self.misses = 0

    def detect(self, frame):
        import cv2
        import numpy as np
        rgb = CameraFrameClient.rgb(frame)
        height, width = rgb.shape[:2]
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, (0, 100, 60), (10, 255, 255)) | cv2.inRange(hsv, (170, 100, 60), (179, 255, 255))
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            area = cv2.contourArea(contour)
            moments = cv2.moments(contour)
            if area < max(30, width * height * .0004) or not moments['m00']:
                continue
            x, y = moments['m10']/moments['m00']/width, moments['m01']/moments['m00']/height
            left, top, w, h = cv2.boundingRect(contour)
            candidates.append({'found': True, 'normalized_x': x, 'normalized_y': y, 'area': area,
                               'box': [left/width, top/height, w/width, h/height]})
        if self.previous is not None and self.misses < 6:
            candidates = [item for item in candidates if hypot(item['normalized_x']-self.previous[0], item['normalized_y']-self.previous[1]) < .22]
            candidates.sort(key=lambda item: hypot(item['normalized_x']-self.previous[0], item['normalized_y']-self.previous[1]))
        else:
            candidates.sort(key=lambda item: -item['area'])
        if not candidates:
            self.misses += 1
            return {'found': False, 'box': None}
        item = candidates[0]
        self.previous = (item['normalized_x'], item['normalized_y'])
        self.misses = 0
        return item

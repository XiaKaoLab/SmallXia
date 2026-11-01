"""通过统一相机 API 获取画面变量，并按需解码为 RGB 数组。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import base64
import json
import os
import re
from io import BytesIO
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from time import monotonic, sleep


class CameraFrameClient:
    def read(self, source: str) -> dict:
        if source not in ('virtual', 'real') and not re.fullmatch(r'opencv_[0-9a-f]{16}', source):
            raise ValueError('请选择已发现的摄像头')
        request = Request(f'http://127.0.0.1:8766/api/v1/cameras/{source}/frame',
                          headers={'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        deadline = monotonic() + 2
        while True:
            try:
                with urlopen(request, timeout=2) as response:
                    return json.load(response)
            except HTTPError as error:
                message = json.loads(error.read()).get('error', str(error))
                if source == 'virtual' and error.code == 409 and monotonic() < deadline:
                    sleep(0.1)
                    continue
                raise RuntimeError(message) from None

    def configure_real(self, device_index: int = 0, enabled: bool = True) -> dict:
        request = Request('http://127.0.0.1:8766/api/v1/cameras/real/config',
                          data=json.dumps({'device_index': device_index, 'enabled': enabled}).encode(),
                          headers={'Content-Type': 'application/json',
                                   'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']}, method='POST')
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    @staticmethod
    def rgb(frame: dict):
        import numpy as np
        from PIL import Image
        with Image.open(BytesIO(base64.b64decode(frame['image_base64']))) as image:
            return np.array(image.convert('RGB'))

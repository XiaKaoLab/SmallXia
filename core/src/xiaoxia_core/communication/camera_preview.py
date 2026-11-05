"""功能：通过统一画面 API 持续预览真实相机，保留来源身份和设备选择。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
import re
from time import monotonic, sleep
from ..blocks.workflow import BlockWorkflow
from ..collection.frame_client import CameraFrameClient


class RealCameraPreview:
    @staticmethod
    def stream(source, emit):
        if source != 'auto' and (not isinstance(source,str) or not re.fullmatch(r'opencv_[0-9a-f]{16}',source)):
            raise ValueError('请选择真实摄像头')
        client=CameraFrameClient()
        devices=[];refresh=0
        while True:
            started=monotonic()
            try:
                if started>=refresh:
                    devices=[row for row in BlockWorkflow.http('cameras')['cameras'] if row.get('physical')]
                    refresh=started+3
                selected=(next((row for row in devices if 'icspring' in row['name'].lower()),None) or (devices[0] if devices else None)) if source=='auto' else next((row for row in devices if row['id']==source),None)
                if selected is None:
                    data={'status':'unavailable','message':'未发现真实相机','cameras':devices}
                else:
                    frame=client.read(selected['id'])
                    if frame.get('physical') is not True:raise ValueError('画面来源不是实拍')
                    data={'status':'ready','source':selected['id'],'name':selected['name'],'physical':True,
                          'image':'data:image/jpeg;base64,'+frame['image_base64'],
                          'width':frame['width'],'height':frame['height'],'sequence':frame.get('sequence'),
                          'timestamp_ns':frame.get('timestamp_ns'),'cameras':devices}
            except Exception as error:
                data={'status':'unavailable','message':str(error),'cameras':devices}
            emit({'type':'camera_preview','data':data})
            sleep(max(.03,.25-(monotonic()-started)))

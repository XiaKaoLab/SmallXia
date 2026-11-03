"""文字识别与文字方块仿真抓取 API，显式区分相机来源和动作范围。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import base64
from io import BytesIO
from math import isfinite
from threading import Lock
import numpy as np
from PIL import Image
from .text_blocks import TextBlockReader


class TextVisionAPI:
    prefix='/api/v1/vision'
    def __init__(self,frames,jobs,models):
        self.frames,self.jobs,self.models=frames,jobs,models
        self.reader=None;self.lock=Lock()

    def handle(self,method,path,body=None):
        body=body or {};endpoint=path.removeprefix(self.prefix).strip('/')
        try:
            if method=='GET' and endpoint=='capabilities':
                return 200,{'recognizer':'RapidOCR_ONNX','vocabulary':'open_text_within_OCR_language_support',
                    'real_camera_reading':True,'real_robot_execution':False,'simulation_pick':True,
                    'requires':['visible_text','unique_target','camera_calibration_for_position','reachable_cube'],
                    'grasp_controller_privileged_state':True}
            if method!='POST':return 404,{'error':'route_not_found'}
            target=body.get('target_text','')
            if not isinstance(target,str) or len(target)>32:raise ValueError('目标文字最多32字')
            if endpoint=='text-recognitions':
                camera=body.get('camera_id','virtual')
                if not isinstance(camera,str):raise ValueError('需要相机 ID')
                frame=self.frames.read(camera)
                with Image.open(BytesIO(base64.b64decode(frame['image_base64']))) as image:rgb=np.asarray(image.convert('RGB'))
                with self.lock:
                    if self.reader is None:self.reader=TextBlockReader()
                    detections=self.reader.read(rgb)
                matches=[x for x in detections if self.reader.normalize(x['text'])==self.reader.normalize(target)] if target else []
                return 200,{'camera_id':camera,'source':frame['source'],'physical':frame['physical'],
                    'timestamp_ns':frame['timestamp_ns'],'detections':detections,'target_text':target,'matches':matches,
                    'unique_match':len(matches)==1,'executed':False}
            if endpoint=='text-picks':
                if not target.strip():raise ValueError('请输入目标文字')
                texts=body.get('texts',[target,*[x for x in ('A','B','C') if TextBlockReader.normalize(x)!=TextBlockReader.normalize(target)][:2]])
                if not isinstance(texts,list) or len(texts)!=3 or any(not isinstance(x,str) or not x.strip() or len(x)>12 for x in texts):
                    raise ValueError('仿真需要三个文字方块，每个1–12字')
                normalized=[TextBlockReader.normalize(x) for x in texts]
                if len(set(normalized))!=3 or TextBlockReader.normalize(target) not in normalized:raise ValueError('方块文字需要互不相同且包含目标')
                rounds=body.get('rounds',1);seed=body.get('seed',42);speed=body.get('playback_speed',1.)
                if type(rounds)is not int or not 1<=rounds<=100:raise ValueError('轮数需要1–100')
                if type(seed)is not int or not 0<=seed<=2147483647:raise ValueError('随机种子无效')
                if type(speed)not in (int,float) or not isfinite(speed) or (speed!=0 and not .1<=speed<=4):raise ValueError('速度需要0或0.1–4倍')
                with self.lock:
                    if any(x['kind'] in ('ball_pickup','ball_onnx_rollout') and x['status'] in ('queued','running') for x in self.jobs.list()):
                        raise ValueError('已有训练或推理在运行，请等待完成')
                    source=self.models.source(body.get('model_job_id','latest'),exported=True)
                    return 202,self.jobs.start('ball_onnx_rollout',{'task_type':'text_pick','target_text':target,
                        'texts':texts,'source_directory':str(source),'rounds':rounds,'seed':seed,'playback_speed':speed},
                        initial_state={'task':f'抓取文字方块 · {target}','num_envs':1,'rounds':rounds,
                            'completed_episodes':0,'total_episodes':rounds,'progress':0,'physical':False})
            return 404,{'error':'route_not_found'}
        except (ValueError,KeyError,FileNotFoundError) as error:return 400,{'error':str(error)}

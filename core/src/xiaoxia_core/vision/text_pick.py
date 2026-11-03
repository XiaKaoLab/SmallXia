"""通用 OCR 选择文字方块，再以已有 ONNX 抓取策略执行独立仿真。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from pathlib import Path
from time import monotonic
import mujoco
import numpy as np
from .text_blocks import TextBlockReader, CalibratedPlane
from ..reinforcement.text_cube_environment import TextCubeEnvironment
from ..reinforcement.ball_observation import BallObservation
from ..reinforcement.preview import TrainingPreviewPublisher
from ..reinforcement.inference_playback import InferencePlayback
from ..inference.ball_onnx import BallOnnxPolicy
from ..imitation.api_jobs import atomic_json


class TextPickSimulation:
    def __init__(self,worker):self.worker=worker;self.request=worker.request

    def run(self):
        from PIL import Image
        policy=BallOnnxPolicy(Path(self.request['source_directory']))
        from ..reinforcement.ball_environment import BallPickupEnvironment
        if policy.state_dim!=31 or policy.manifest.get('environment_version') != BallPickupEnvironment.version:
            raise ValueError('需要当前版本31维腕部相机抓取模型')
        reader=TextBlockReader()
        scene=type('TextCubeScene',(TextCubeEnvironment,),{'display_texts':tuple(self.request['texts'])})
        root=Path(__file__).resolve().parents[4]
        env=scene.vector(root/'table/public/robots/so101/so101_new_calib.urdf',1,self.request['seed'])[0]
        renderer=observer=None
        episodes=[];preview=TrainingPreviewPublisher(self.worker.directory,kind='ball_onnx_rollout')
        playback=InferencePlayback(self.request.get('playback_speed',1.),self.worker)
        env.playback_checkpoint=playback.checkpoint
        try:
            renderer=mujoco.Renderer(env._model,height=1024,width=1024)
            observer=BallObservation(env,self.request['seed']+100000,noisy=False)
            for episode in range(self.request['rounds']):
                env.reset_episode();preview.publish([env],force=True)
                renderer.update_scene(env._data,camera='letter_overhead');rgb=renderer.render().copy()
                Image.fromarray(rgb).save(self.worker.directory/f'observation-{episode:03d}.png')
                preview.set_camera_frame(rgb.transpose(2,0,1),float(env._data.time),camera='letter_overhead',source='ocr_observation');preview.publish([env],force=True)
                self.worker.progress(phase='recognizing',target_text=self.request['target_text'])
                try:selected,detections=reader.select(rgb,self.request['target_text'])
                except ValueError as error:
                    episodes.append({'recognized':False,'success':False,'reason':str(error),'moved':False})
                    self.worker.progress(completed_episodes=episode+1,progress=(episode+1)/self.request['rounds'])
                    continue
                camera=mujoco.mj_name2id(env._model,mujoco.mjtObj.mjOBJ_CAMERA,'letter_overhead')
                center=rgb.shape[0]/2
                focal=center/np.tan(np.deg2rad(env._model.cam_fovy[camera])/2)
                k=[[focal,0,center],[0,focal,center],[0,0,1]]
                transform=np.eye(4);transform[:3,:3]=env._data.cam_xmat[camera].reshape(3,3)@np.diag([1,-1,-1]);transform[:3,3]=env._data.cam_xpos[camera]
                point=CalibratedPlane(k,transform,env.floor_z+env.half_size*2).locate(selected['pixel_center'])
                # 视觉只输出像素/世界位置；绑定最近的模拟刚体只用于既有控制器与物理验收。
                body=min(env.letter_bodies.values(),key=lambda b:np.linalg.norm(env._data.xpos[b][:2]-point[:2]))
                error=float(np.linalg.norm(env._data.xpos[body][:2]-point[:2]))
                if error>.02:raise ValueError('文字定位不在方块范围内，不执行抓取')
                actual_text=scene.display_texts[scene.letters.index(next(k for k,v in env.letter_bodies.items() if v==body))]
                env.select_body(body)
                selection={'requested_text':self.request['target_text'],'recognized':selected,'detections':detections,
                    'world_position':point.tolist(),'image_resolution':[int(rgb.shape[1]),int(rgb.shape[0])],'simulation_binding_error_m':error,'source':'simulation_overhead',
                    'selected_actual_text_for_evaluation':actual_text,'controller_privileged_state':True}
                atomic_json(self.worker.directory/f'selection-{episode:03d}.json',selection)
                self.worker.progress(phase='inferencing',selection=selection)
                peak_force=0.;success=False;last_camera=0.
                while not env.ended:
                    started=monotonic();simulation_time=float(env._data.time)
                    observation=observer.read()
                    if monotonic()-last_camera>=.25:
                        renderer.update_scene(env._data,camera='letter_overhead')
                        frame=renderer.render().copy()
                        preview.set_camera_frame(frame.transpose(2,0,1),simulation_time,camera='letter_overhead',source='ocr_observation')
                        last_camera=monotonic()
                    action=policy.predict(np.asarray([observation['observation.state']]),np.asarray([observation[observer.camera_key]],dtype=np.float32)/255)[0]
                    _,_,_,_,success=env.advance(action);observer.read();preview.publish([env])
                    peak_force=max(peak_force,env.contact_state()['arm_floor_force'])
                    self.worker.progress(phase='inferencing',current_score=env.return_,snapshot=env.snapshot(),
                        completed_episodes=episode,progress=episode/self.request['rounds'])
                    playback.wait_step(started,float(env._data.time)-simulation_time)
                correct=reader.normalize(actual_text)==reader.normalize(self.request['target_text'])
                accepted=bool(success and correct and peak_force<=5.)
                episodes.append({'recognized':True,'selected_correctly':correct,'success':accepted,'physical_grasp':bool(success),
                    'selection':selection,'score':env.return_,'peak_arm_floor_force':peak_force,'snapshot':env.snapshot()})
                self.worker.progress(completed_episodes=episode+1,progress=(episode+1)/self.request['rounds'],
                    successes=sum(x['success'] for x in episodes),score=env.return_,snapshot=env.snapshot())
                if episode+1<self.request['rounds']:playback.pause_episode()
            return {'target_text':self.request['target_text'],'completed_episodes':len(episodes),
                'recognized_episodes':sum(x['recognized'] for x in episodes),'successes':sum(x['success'] for x in episodes),
                'episodes':episodes,'recognizer':'RapidOCR_ONNX','controller':'existing_grasp_ONNX',
                'controller_privileged_state':True,'physical':False,'training':False}
        finally:
            if observer:observer.close()
            if renderer:renderer.close()
            env.disconnect()

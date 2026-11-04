"""功能：提供只读、分步自动采样的六轴控制坐标标定 API，不改写电机参数。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
import hashlib
import json
from math import pi
from pathlib import Path
from statistics import median
from threading import RLock
from time import sleep, time
from uuid import uuid4
from ..safety import JOINTS
from ..imitation.workflows import HardwareWorkflow
from ..imitation.api_jobs import atomic_json, identifier
from ..communication.calibration import ArmCalibration
from ..communication.official_calibration import OfficialCalibrationStore


class CoordinateCalibrationAPI:
    """客户端显示 reference_rad，操作者确认姿态和正方向；服务负责读数和计算。"""
    def __init__(self, core, hardware):
        self.core=Path(core);self.hardware=hardware;self.lock=RLock()
        self.root=self.core/'data/coordinate_calibration';self.root.mkdir(parents=True,exist_ok=True)

    def workflow(self, profile):
        if not isinstance(profile,str) or Path(profile).name!=profile or not profile.endswith('.yaml'):
            raise ValueError('请选择机械臂配置')
        return HardwareWorkflow(self.core/'configs'/profile)

    @staticmethod
    def fingerprint(workflow):
        payload=json.dumps(workflow.config,sort_keys=True).encode()+workflow.path(workflow.config['follower']['calibration']).read_bytes()
        return hashlib.sha256(payload).hexdigest()

    def sample(self, workflow):
        from lerobot.motors import Motor, MotorNormMode
        from lerobot.motors.feetech import FeetechMotorsBus
        class ReadOnlyBus(FeetechMotorsBus):
            def write(self,*a,**k):raise ValueError('标定采样禁止写入电机')
            def sync_write(self,*a,**k):raise ValueError('标定采样禁止写入电机')
            def enable_torque(self,*a,**k):raise ValueError('标定采样禁止改动力矩')
            def disable_torque(self,*a,**k):raise ValueError('标定采样禁止改动力矩')
        port=workflow.config['follower']['port']
        if port in self.hardware.sessions:raise ValueError('请先停止真机控制')
        bus=ReadOnlyBus(port,{n:Motor(i,'sts3215',MotorNormMode.DEGREES) for i,n in enumerate(JOINTS,1)})
        try:
            bus.connect();bus.set_timeout(150)
            expected=OfficialCalibrationStore.validate(json.loads(workflow.path(workflow.config['follower']['calibration']).read_text(encoding='utf-8')))
            if {n:vars(v) for n,v in bus.read_calibration().items()}!=expected:
                raise ValueError('设备与官方校准不匹配，请先完成官方校准')
            samples=[]
            for _ in range(12):
                if any(bus.sync_read('Torque_Enable',normalize=False).values()):raise ValueError('请先安全支撑机械臂并关闭力矩')
                samples.append(bus.sync_read('Present_Position',normalize=False));sleep(.04)
            spread={n:max(s[n] for s in samples)-min(s[n] for s in samples) for n in JOINTS}
            # 中值滤波允许轻微手持抖动；跨编码器边界或持续移动不会被当作稳定零点。
            if max(spread.values())>24:raise ValueError('请保持姿态，稍后自动重试采样')
            return {n:median(s[n] for s in samples) for n in JOINTS},spread
        finally:
            if bus.is_connected:bus.disconnect(disable_torque=False)

    def load(self, sid):
        path=self.root/(identifier(sid)+'.json')
        state=json.loads(path.read_text(encoding='utf-8'))
        if state['stage'] not in ('saved','cancelled') and time()-state['updated_at']>1800:
            raise ValueError('测量已过期，请重新开始')
        return path,state

    def start(self, body):
        workflow=self.workflow(body.get('profile','so100.local.yaml'))
        if body.get('port')!=workflow.config['follower']['port']:raise ValueError('配置与串口不一致')
        state={'id':uuid4().hex,'profile':body.get('profile','so100.local.yaml'),'port':body['port'],
            'stage':'zero','instruction':'请对齐参考姿态','reference_rad':dict.fromkeys(JOINTS,0),
            'joints':{},'writes_to_device':0,'verified':False,'updated_at':time(),
            'fingerprint':self.fingerprint(workflow)}
        atomic_json(self.root/(state['id']+'.json'),state);return state

    def advance(self, sid, body):
        path,state=self.load(sid)
        if state['stage'] not in ('zero','direction'):raise ValueError('当前步骤无需采样')
        required='pose_confirmed' if state['stage']=='zero' else 'positive_direction_confirmed'
        if body.get(required) is not True:raise ValueError('请确认参考姿态或本轴正方向')
        workflow=self.workflow(state['profile'])
        if self.fingerprint(workflow)!=state['fingerprint']:raise ValueError('校准配置已改变，请重新开始')
        ticks,spread=self.sample(workflow)
        if state['stage']=='zero':
            state['joints']={n:{'zero_tick':ticks[n],'direction':None} for n in JOINTS}
            state['zero_spread_ticks']=spread;state['stage']='direction';state['index']=0
        else:
            name=JOINTS[state['index']];delta=ticks[name]-state['joints'][name]['zero_tick']
            if not 35<=abs(delta)<=350:raise ValueError('请从参考姿态沿提示方向转动约5至20度')
            state['joints'][name].update(direction=1 if delta>0 else -1,positive_sample_tick=ticks[name])
            state['index']+=1
            if state['index']==len(JOINTS):state['stage']='review'
        if state['stage']=='direction':
            name=JOINTS[state['index']]
            state.update(joint=name,reference_rad={n:(10*pi/180 if n==name else 0) for n in JOINTS},instruction='请沿模型正方向转动当前关节')
        else:
            state.pop('joint',None);state.update(reference_rad=dict.fromkeys(JOINTS,0),instruction='确认并保存')
        state['updated_at']=time();atomic_json(path,state);return state

    def save(self,sid,body):
        path,state=self.load(sid)
        if state['stage']=='saved':return state
        if state['stage']!='review' or body.get('confirmed') is not True:raise ValueError('请先完成六轴测量并确认')
        workflow=self.workflow(state['profile'])
        if self.fingerprint(workflow)!=state['fingerprint']:raise ValueError('校准配置已改变，请重新开始')
        self.sample(workflow)  # 保存前再次检查 EEPROM 身份及只读状态。
        candidate=self.root/(sid+'.mapping.json')
        mapping={'verified':True,'joints':{n:{k:state['joints'][n][k] for k in ('zero_tick','direction')} for n in JOINTS},'measurement_id':sid}
        atomic_json(candidate,mapping)
        ArmCalibration.load(workflow.path(workflow.config['follower']['calibration']),candidate,workflow.limits)
        target=workflow.path(workflow.config['follower']['mapping'])
        if target.exists():atomic_json(self.root/(sid+'.previous.json'),json.loads(target.read_text(encoding='utf-8')))
        atomic_json(target,mapping)
        state.update(stage='saved',instruction='已保存',verified=True,close_panel=True,updated_at=time())
        atomic_json(path,state);return state

    def handle(self, method, endpoint, body):
        with self.lock,self.hardware.lock:
            parts=endpoint.split('/')
            if method=='POST' and len(parts)==1:return 201,self.start(body)
            sid=parts[1] if len(parts)>1 else ''
            if method=='GET' and len(parts)==2:return 200,self.load(sid)[1]
            if method=='POST' and len(parts)==3:
                if parts[2]=='sample':return 200,self.advance(sid,body)
                if parts[2]=='save':return 200,self.save(sid,body)
                if parts[2]=='cancel':
                    path,state=self.load(sid)
                    if state['stage']=='saved':raise ValueError('已保存的配置不能通过取消撤销')
                    state.update(stage='cancelled',instruction='已取消',updated_at=time());atomic_json(path,state);return 200,state
            return 404,{'error':'route_not_found'}

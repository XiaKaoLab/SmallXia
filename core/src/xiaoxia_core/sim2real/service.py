"""Sim2Real 一期：只读坐标预检、真实反馈与单次小幅限速动作，复用已验证硬件控制。
Created on 2026-11-03; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
from pathlib import Path
from math import isfinite,pi
from threading import RLock
import json,re,hashlib
from ..safety import JOINTS
from ..imitation.workflows import HardwareWorkflow


class CoordinateIdentity:
    @staticmethod
    def fingerprint(workflow):
        follower=workflow.config['follower']
        digest=hashlib.sha256(json.dumps(workflow.config,sort_keys=True).encode('utf-8'))
        for key in (('calibration',) if workflow.config.get('coordinate_basis')=='official_calibration' else ('calibration','mapping')):digest.update(workflow.path(follower[key]).read_bytes())
        if follower.get('zero_reference'):digest.update(workflow.path(follower['zero_reference']).read_bytes())
        digest.update(workflow.path(workflow.config['urdf']).read_bytes())
        return digest.hexdigest()


class Sim2RealAPI:
    prefix='/api/v1/sim2real'
    max_step_rad=pi/18
    max_velocity_rad_s=.15

    def __init__(self,core,hardware):
        self.core=Path(core);self.hardware=hardware;self.lock=RLock()
        from .coordinate_calibration import CoordinateCalibrationAPI
        self.coordinates=CoordinateCalibrationAPI(core,hardware)

    def check(self,port,profile='so100.local.yaml'):
        if not isinstance(port,str) or not re.fullmatch(r'COM[1-9][0-9]*',port):raise ValueError('请选择机械臂 COM 口')
        if not isinstance(profile,str) or Path(profile).name!=profile or not profile.endswith('.yaml'):raise ValueError('请选择本机机械臂配置')
        report={'port':port,'profile':profile,'physical':True,'device_opened':False,'writes':0,
            'torque_enabled_by_check':False,'unit':'rad','max_step_rad':self.max_step_rad,
            'max_velocity_rad_s':self.max_velocity_rad_s,'blockers':[],'joints':{},'eeprom_match':'not_checked'}
        blockers=report['blockers']
        try:
            workflow=HardwareWorkflow(self.core/'configs'/profile)
            config=workflow.config
            if config['follower']['port']!=port:blockers.append('配置与所选串口不一致')
            expected=(self.core.parent/'table/public/robots/so100/so100_mid_calib.urdf').resolve()
            if workflow.path(config['urdf'])!=expected:blockers.append('仿真与真机 URDF 坐标不一致')
            speed=config.get('max_velocity_rad_s',.25)
            if type(speed)not in (int,float) or not isfinite(speed) or not 0<speed<=self.max_velocity_rad_s:
                blockers.append('一期真机速度需在0–0.15弧度/秒内')
            report['configured_velocity_rad_s']=speed
            follower=config['follower']
            native=config.get('coordinate_basis')=='official_calibration'
            calibration_path=workflow.path(follower['calibration'])
            mapping_path=None if native else workflow.path(follower['mapping'])
            raw=json.loads(calibration_path.read_text(encoding='utf-8'))
            report['coordinate_basis']='official_calibration' if native else 'urdf'
            mapping={} if native else json.loads(mapping_path.read_text(encoding='utf-8'))
            report['official_calibration_available']=set(raw)==set(JOINTS)
            if not report['official_calibration_available']:blockers.append('官方校准文件不完整')
            report['mapping_verified']=mapping.get('verified') is True
            if not native and not report['mapping_verified']:blockers.append('六轴运动坐标尚未确认')
            missing=[]
            for name in JOINTS:
                item=mapping.get('joints',{}).get(name,{})
                zero,direction=item.get('zero_tick'),item.get('direction')
                valid=type(zero)in(int,float) and isfinite(zero) and type(direction)is int and direction in (-1,1)
                if not valid:missing.append(name)
                report['joints'][name]={'zero_tick':zero,'direction':direction,'mapping_complete':valid}
            if missing and not native:blockers.append('请确认六轴的实测零点和编码器方向')
            report['missing_mapping_joints']=missing
            report['coordinate_fingerprint']=CoordinateIdentity.fingerprint(workflow)
            if not blockers:
                arm=workflow.arm('follower')  # 只读文件并构造适配器，不 connect、不 arm。
                report['zero_source']=getattr(arm.calibration,'zero_source','measured_urdf')
                report['zero_ticks']={name:j.zero_tick for name,j in arm.calibration.joints.items()}
                report['mapping_required']=not native
                report['limits']={name:{'lower':v.lower,'upper':v.upper,'unit':'rad'} for name,v in arm.limits.joints.items()}
        except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as error:blockers.append(str(error))
        with self.hardware.lock:
            session=self.hardware.sessions.get(port)
            state=session.snapshot() if session else None
        if state and state['status'] in ('ready','moving') and state.get('coordinate_fingerprint')!=report.get('coordinate_fingerprint'):
            blockers.append('控制会话坐标配置已变化，请先释放再重新连接')
        report['ready_for_connection']=not blockers
        report['control_connected']=bool(state and state['status'] in ('ready','moving'))
        report['ready_for_motion']=bool(not blockers and report['control_connected'] and state.get('profile')==profile
            and state.get('feedback_age_ms') is not None and state['feedback_age_ms']<=500)
        if state:
            report['feedback']=state
            if report['control_connected'] and state.get('profile')==profile:report['eeprom_match']='matched_on_connection'
        return report

    def state(self,port,profile):
        report=self.check(port,profile)
        return {'target':f'serial:{port}','physical':True,'source':'hardware_feedback' if report['control_connected'] else 'preflight',
            'unit':'rad','joint_positions':(report.get('feedback')or{}).get('joint_positions'),
            'ready':report['ready_for_motion'],'preflight':report}

    def move(self,body):
        if body.get('enable_motion') is not True:raise ValueError('真机运动尚未启用')
        port,profile=body.get('port'),body.get('profile','so100.local.yaml')
        report=self.check(port,profile)
        if not report['ready_for_motion']:raise ValueError('；'.join(report['blockers']) or '真机反馈未就绪或已过期')
        positions=body.get('joint_positions')
        if body.get('unit')!='rad' or not isinstance(positions,dict) or set(positions)!=set(JOINTS) or any(type(v)not in(int,float) or not isfinite(v) for v in positions.values()):
            raise ValueError('需要完整六轴弧度目标')
        with self.lock,self.hardware.lock:
            session=self.hardware.sessions[port]
            with session.lock:
                state=session.snapshot()
                if state['status']!='ready' or state.get('profile')!=profile or state.get('coordinate_fingerprint')!=report.get('coordinate_fingerprint') or state.get('feedback_age_ms',501)>500:raise ValueError('请等待真机稳定且反馈新鲜')
                current=state['joint_positions']
                if max(abs(positions[name]-current[name]) for name in JOINTS)>self.max_step_rad+1e-6:
                    raise ValueError('一期每条消息各关节最多移动10度')
                session.arm.limits.validate(positions)
                session.guard.assert_path(current,positions)
                result=session.move({'joint_positions':positions,'unit':'rad'})
        return {**result,'accepted':True,'arrived':False,'source':'sim2real_guarded_target','physical':True}

    def handle(self,method,path,body=None):
        body=body or {};endpoint=path.removeprefix(self.prefix).strip('/')
        try:
            if endpoint=='calibrations' or endpoint.startswith('calibrations/'):
                return self.coordinates.handle(method,endpoint,body)
            if method=='POST' and endpoint=='checks':return 200,self.check(body.get('port'),body.get('profile','so100.local.yaml'))
            if method=='POST' and endpoint=='state':return 200,self.state(body.get('port'),body.get('profile','so100.local.yaml'))
            if method=='POST' and endpoint=='motions':return 202,self.move(body)
            return 404,{'error':'route_not_found'}
        except (ValueError,KeyError,TypeError,OSError) as error:return 422,{'error':str(error)}

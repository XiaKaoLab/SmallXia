"""器灵绑定串口后的真实机械臂工具：预检、反馈、单消息一次小幅运动。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from time import monotonic,sleep
import re
from ..blocks.workflow import BlockWorkflow


class Sim2RealTools:
    def __init__(self,target,profile,motion_enabled):
        if not isinstance(target,str) or not re.fullmatch(r'serial:COM[1-9][0-9]*',target):raise ValueError('器灵未绑定有效串口')
        self.port=target[7:];self.profile=profile;self.motion_enabled=motion_enabled;self.motion_used=False

    def request(self,endpoint,**values):
        return BlockWorkflow.http('sim2real/'+endpoint,{'port':self.port,'profile':self.profile,**values})

    def arm_get_state(self)->dict:
        """查询绑定真机的控制反馈与坐标预检。无连接时仅报告未就绪，不打开串口、不使能、不用仿真值填充反馈。"""
        return self.request('state')

    def arm_get_limits(self)->dict:
        """读取已验证的真机编码器/URDF相交限位(rad)，同时报告一期单次10度和0.15rad/s速度上限。"""
        report=self.request('checks')
        if not report['ready_for_connection']:raise ValueError('；'.join(report['blockers']))
        return {'physical':True,'port':self.port,'unit':'rad','limits':report['limits'],
            'max_step_rad':report['max_step_rad'],'max_velocity_rad_s':report['configured_velocity_rad_s']}

    def arm_move_joints(self,shoulder_pan:float,shoulder_lift:float,elbow_flex:float,
                        wrist_flex:float,wrist_roll:float,gripper:float)->dict:
        """向已显式启用且预检通过的绑定真机发送六轴绝对弧度目标。先读实测状态/限位，每轴最多10度、速度不超过0.15rad/s。每条消息只提交一次，等待反馈；错误/超时不重发。"""
        if not self.motion_enabled:raise ValueError('未启用真机运动')
        if self.motion_used:raise ValueError('本条消息已提交过真机运动，不可重复发送')
        self.motion_used=True
        target=dict(shoulder_pan=shoulder_pan,shoulder_lift=shoulder_lift,elbow_flex=elbow_flex,
            wrist_flex=wrist_flex,wrist_roll=wrist_roll,gripper=gripper)
        self.request('motions',joint_positions=target,unit='rad',enable_motion=True)
        deadline=monotonic()+8
        while monotonic()<deadline:
            result=self.request('state')
            positions=result.get('joint_positions')
            if result['ready'] and positions and max(abs(positions[name]-target[name]) for name in target)<=.025:
                return {**result,'arrived':True,'tolerance_rad':.025,'target_positions':target}
            feedback=result.get('preflight',{}).get('feedback',{})
            if feedback.get('status') in ('failed','stopped'):raise RuntimeError('真机控制已停止，请检查反馈，不重发动作')
            sleep(.1)
        BlockWorkflow.http(f'hardware/arms/{self.port}/stop',{})
        raise TimeoutError('真机反馈未在8秒内到位，已请求释放控制，不重发动作')

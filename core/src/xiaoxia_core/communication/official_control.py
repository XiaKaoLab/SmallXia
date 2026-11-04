"""功能：以已匹配 EEPROM 的官方校准直接提供绝对角度控制，不要求 URDF 显示映射。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
import json
from hashlib import sha256
from math import pi,isfinite
from ..contracts import Action
from .calibration import ArmCalibration,EncoderJoint
from .official_calibration import OfficialCalibrationStore
from ..safety import JOINTS,JointLimit,JointLimits

class OfficialJointLimits(JointLimits):
    def constrain(self,desired,current,dt,max_velocity):
        self.validate(desired.joint_positions)
        if set(current)!=set(JOINTS) or not all(isfinite(v) for v in current.values()):raise ValueError('六轴反馈无效')
        if not isfinite(dt) or dt<=0:raise ValueError('控制周期无效')
        return Action({n:current[n]+max(-min(self.joints[n].velocity,max_velocity)*dt,min(min(self.joints[n].velocity,max_velocity)*dt,desired.joint_positions[n]-current[n])) for n in JOINTS})

class OfficialArmCalibration(ArmCalibration):
    def __init__(self,path,zero_reference=None):
        reference=json.loads(zero_reference.read_text(encoding="utf-8")) if zero_reference else None
        if reference and reference["calibration_sha256"]!=sha256(path.read_bytes()).hexdigest():raise ValueError("零位记录与设备校准不匹配")
        self.zero_source="user_declared_current_pose" if reference else "official_calibration"
        raw=OfficialCalibrationStore.validate(json.loads(path.read_text(encoding='utf-8')))
        self.joints={};self.tick_bounds={};self.render_offsets={};self.raw_calibration=raw;limits={}
        for name in JOINTS:
            row=raw[name]
            zero=reference['zero_ticks'][name] if reference else (row['range_min'] if name=='gripper' else (row['range_min']+row['range_max'])/2)
            model_zero=row['range_min'] if name=='gripper' else (row['range_min']+row['range_max'])/2
            self.render_offsets[name]=(zero-model_zero)*2*pi/4095
            joint=EncoderJoint(row['id'],row['homing_offset'],row['range_min'],row['range_max'],zero,1)
            self.joints[name]=joint;self.tick_bounds[name]=(row['range_min'],row['range_max'])
            limits[name]=JointLimit(joint.angle(row['range_min']),joint.angle(row['range_max']),1,35)
        self.limits=OfficialJointLimits(limits)

    def render_angles(self,positions):
        return {n:v+self.render_offsets[n] for n,v in positions.items()}

    def angles(self,ticks):
        if set(ticks)!=set(JOINTS) or any(not isfinite(v) or not 0<=v<=4095 for v in ticks.values()):raise ValueError('编码器反馈无效')
        self.last_raw_ticks=dict(ticks)
        return {n:self.joints[n].angle(v) for n,v in ticks.items()}

    def ticks(self,positions):
        # 轨迹可能从校准端点外的真实起点向区间内恢复；目标入口仍按校准行程检查。
        ticks={n:self.joints[n].tick(v) for n,v in positions.items()}
        if set(ticks)!=set(JOINTS) or any(not 0<=v<=4095 for v in ticks.values()):raise ValueError('编码器目标越界')
        return ticks

class OfficialJointGuard:
    """官方关节空间仅检查实测机械行程，不冒充 URDF 几何碰撞校验。"""
    def __init__(self,limits):self.limits=limits
    def assert_pose(self,positions):
        if set(positions)!=set(JOINTS) or not all(isfinite(v) for v in positions.values()):raise ValueError("六轴反馈无效")
    def assert_path(self,start,target):self.assert_pose(start);self.limits.validate(target)
    def limit_path(self,start,target):self.assert_path(start,target);return dict(target),''

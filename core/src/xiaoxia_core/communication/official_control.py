"""功能：以已匹配 EEPROM 的官方校准直接提供绝对角度控制，不要求 URDF 显示映射。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
import json
from math import pi
from .calibration import ArmCalibration,EncoderJoint
from .official_calibration import OfficialCalibrationStore
from ..safety import JOINTS,JointLimit,JointLimits

class OfficialArmCalibration(ArmCalibration):
    def __init__(self,path):
        raw=OfficialCalibrationStore.validate(json.loads(path.read_text(encoding='utf-8')))
        self.joints={};self.tick_bounds={};limits={}
        for name in JOINTS:
            row=raw[name]
            zero=row['range_min'] if name=='gripper' else (row['range_min']+row['range_max'])/2
            joint=EncoderJoint(row['id'],row['homing_offset'],row['range_min'],row['range_max'],zero,1)
            self.joints[name]=joint;self.tick_bounds[name]=(row['range_min'],row['range_max'])
            limits[name]=JointLimit(joint.angle(row['range_min']),joint.angle(row['range_max']),1,35)
        self.limits=JointLimits(limits)

    def angles(self,ticks):
        # 端点反馈有数个刻度抖动；只在8刻度内按官方端点计算，不扩大目标行程。
        bounded={}
        for name,value in ticks.items():
            low,high=self.tick_bounds[name]
            if value<low-8 or value>high+8:raise ValueError(f'{name} 实测位置超出官方校准行程')
            bounded[name]=max(low,min(high,value))
        self.last_raw_ticks=dict(ticks)
        return super().angles(bounded)

class OfficialJointGuard:
    """官方关节空间仅检查实测机械行程，不冒充 URDF 几何碰撞校验。"""
    def __init__(self,limits):self.limits=limits
    def assert_pose(self,positions):self.limits.validate(positions)
    def assert_path(self,start,target):self.assert_pose(start);self.assert_pose(target)
    def limit_path(self,start,target):self.assert_path(start,target);return dict(target),''

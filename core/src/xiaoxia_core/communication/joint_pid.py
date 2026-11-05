"""功能：关节外环 PID 阻尼与稳态锁定，抑制编码器噪声和微小目标跳动。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from math import exp, pi, radians, isfinite
from .joint_trajectory import JointTrajectory


class JointPID:
    """电机已有位置闭环；负载轴只在轨迹停止后缓慢补偿稳态误差。"""
    tick = 2*pi/4095
    def __init__(self, positions, speed, kp=.12, ki=0., kd=.015, compensation=None):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.compensation = self.validate_compensation(compensation, positions)
        self.filtered = dict(positions)
        self.velocity = dict.fromkeys(positions, 0.)
        self.integral = dict.fromkeys(positions, 0.)
        self.targets = dict(positions)
        self.settled = dict.fromkeys(positions, 0)
        self.locked = dict.fromkeys(positions, False)
        self.command = JointTrajectory(positions, speed)

    @staticmethod
    def validate_compensation(compensation, joints):
        result = {}
        for name, settings in (compensation or {}).items():
            if name not in joints:
                raise ValueError('PID 补偿关节不存在：'+name)
            ki, maximum = settings['ki'], settings['max_trim_deg']
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) or v <= 0 for v in (ki, maximum)):
                raise ValueError('PID 积分增益与补偿角度必须为有限正数')
            kp, kd = settings.get('kp'), settings.get('kd')
            if any(v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) or v < 0) for v in (kp, kd)):
                raise ValueError('PID 比例及微分增益必须为有限非负数')
            result[name] = (ki, radians(maximum), kp, kd)
        return result

    def target(self, requested):
        for name, value in requested.items():
            if abs(value-self.targets[name]) >= 2*self.tick:
                self.targets[name] = value
                self.locked[name] = False
                self.settled[name] = 0
                self.integral[name] = 0.
        return dict(self.targets)

    def step(self, reference, measured, dt, speed):
        dt = max(.0001, min(dt, .05))
        alpha = 1-exp(-dt/.06)
        damping = 1-exp(-dt/.10)
        corrected = {}
        for name, setpoint in reference.items():
            old = self.filtered[name]
            self.filtered[name] += alpha*(measured[name]-old)
            derivative = (self.filtered[name]-old)/dt
            self.velocity[name] += damping*(derivative-self.velocity[name])
            remaining = self.targets[name]-measured[name]
            if self.locked[name] and abs(remaining) <= 4*self.tick:
                corrected[name] = self.command.positions[name]
                continue
            self.locked[name] = False
            close = abs(remaining) <= 3*self.tick and abs(setpoint-self.targets[name]) <= self.tick and abs(self.velocity[name]) < .005
            self.settled[name] = self.settled[name]+1 if close else 0
            if self.settled[name] >= 5 and abs(self.command.velocity[name]) < .01:
                self.locked[name] = True
                corrected[name] = self.command.positions[name]
                continue
            error = setpoint-self.filtered[name]
            if abs(error) <= self.tick:
                error = 0.
            ki, maximum, kp, kd = self.compensation.get(name, (self.ki, 4*self.tick, None, None))
            kp = self.kp if kp is None else kp
            kd = self.kd if kd is None else kd
            integral_limit = maximum/ki if ki else .02
            # 运动期间不积累补偿；仅在参考轨迹到位且反馈速度低时补偿负载。
            compensate = abs(setpoint-self.targets[name]) <= self.tick and abs(self.velocity[name]) < .04
            proposal = max(-integral_limit, min(integral_limit,
                           self.integral[name]+error*dt if compensate else self.integral[name]))
            trim = kp*error + ki*proposal - kd*self.velocity[name]
            # 饱和后只允许有助于退出饱和的积分，避免长期顶住限幅。
            if abs(trim) < maximum or trim*error < 0:
                self.integral[name] = proposal
            corrected[name] = setpoint+max(-maximum, min(maximum, trim))
        self.command.speed = speed
        return self.command.step(corrected, dt)

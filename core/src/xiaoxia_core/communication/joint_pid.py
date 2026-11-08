"""功能：关节外环 PID 阻尼与稳态锁定，抑制编码器噪声和微小目标跳动。
Created on 2026-11-05; Updated on 2026-11-08
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
        self.reference = dict(positions)
        self.trim = dict.fromkeys(positions, 0.)
        self.moving = dict.fromkeys(positions, False)
        self.target_age = dict.fromkeys(positions, 1.)
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
                self.target_age[name] = 0.
                # 连续滑条/策略目标沿用已建立的负载补偿，避免反复卸载再补偿。
        return dict(self.targets)

    def step(self, reference, measured, dt, speed):
        dt = max(.0001, min(dt, .05))
        alpha = 1-exp(-dt/.06)
        damping = 1-exp(-dt/.10)
        corrected = {}
        for name, setpoint in reference.items():
            reference_speed = (setpoint-self.reference[name])/dt
            self.reference[name] = setpoint
            self.target_age[name] += dt
            moving = self.target_age[name] < .25 or abs(reference_speed) > .005 or abs(setpoint-self.targets[name]) > self.tick
            self.moving[name] = moving
            old = self.filtered[name]
            self.filtered[name] += alpha*(measured[name]-old)
            derivative = (self.filtered[name]-old)/dt
            self.velocity[name] += damping*(derivative-self.velocity[name])
            remaining = self.targets[name]-measured[name]
            if not moving and self.locked[name] and abs(remaining) <= 4*self.tick:
                corrected[name] = self.command.positions[name]
                continue
            self.locked[name] = False
            close = not moving and abs(remaining) <= 3*self.tick and abs(self.velocity[name]) < .005
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
            compensate = not moving and abs(self.velocity[name]) < .04
            proposal = max(-integral_limit, min(integral_limit,
                           self.integral[name]+error*dt if compensate else self.integral[name]))
            # 运动时交由舵机位置内环跟踪平滑参考，只保留负载偏置。
            # 静止后才启用位置精修，避免把正常跟随滞后当作稳态误差。
            trim = ki*proposal if moving else kp*error + ki*proposal - kd*self.velocity[name]
            # 饱和后只允许有助于退出饱和的积分，避免长期顶住限幅。
            if abs(trim) < maximum or trim*error < 0:
                self.integral[name] = proposal
            desired_trim = max(-maximum, min(maximum, trim))
            # 补偿进退独立限速，不因目标更新或运动/保持切换突然改变目标位置。
            trim_step = min(.02, speed*.25)*dt
            self.trim[name] += max(-trim_step, min(trim_step, desired_trim-self.trim[name]))
            corrected[name] = setpoint+self.trim[name]
        self.command.speed = speed
        return self.command.step(corrected, dt)

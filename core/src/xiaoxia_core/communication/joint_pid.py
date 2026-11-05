"""功能：关节外环 PID 阻尼与稳态锁定，抑制编码器噪声和微小目标跳动。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from math import exp, pi
from .joint_trajectory import JointTrajectory


class JointPID:
    """电机已有位置闭环；外环只做小幅修正，默认关闭积分，避免双重积分累积。"""
    tick = 2*pi/4095

    def __init__(self, positions, speed, kp=.12, ki=0., kd=.015):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.filtered = dict(positions)
        self.velocity = dict.fromkeys(positions, 0.)
        self.integral = dict.fromkeys(positions, 0.)
        self.targets = dict(positions)
        self.settled = dict.fromkeys(positions, 0)
        self.locked = dict.fromkeys(positions, False)
        self.command = JointTrajectory(positions, speed)

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
            if self.locked[name] and abs(remaining) <= 6*self.tick:
                corrected[name] = self.command.positions[name]
                continue
            self.locked[name] = False
            close = abs(remaining) <= 2*self.tick and abs(setpoint-self.targets[name]) <= self.tick
            self.settled[name] = self.settled[name]+1 if close else 0
            if self.settled[name] >= 5 and abs(self.command.velocity[name]) < .01:
                self.locked[name] = True
                self.integral[name] = 0.
                corrected[name] = self.command.positions[name]
                continue
            error = setpoint-self.filtered[name]
            if abs(error) <= 2*self.tick:
                error = 0.
                self.integral[name] = 0.
            proposal = max(-.02, min(.02, self.integral[name]+error*dt))
            trim = self.kp*error + self.ki*proposal - self.kd*self.velocity[name]
            maximum = 4*self.tick
            if abs(trim) < maximum:
                self.integral[name] = proposal
            corrected[name] = setpoint+max(-maximum, min(maximum, trim))
        self.command.speed = speed
        return self.command.step(corrected, dt)

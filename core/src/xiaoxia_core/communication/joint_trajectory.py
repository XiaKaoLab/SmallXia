"""功能：关节目标加减速平滑，保留浮点轨迹并避免编码器量化造成启停抖动。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
from math import sqrt,copysign

class JointTrajectory:
    def __init__(self,positions,speed,acceleration=.3):
        self.positions=dict(positions);self.velocity=dict.fromkeys(positions,0.0)
        self.speed=speed;self.acceleration=acceleration

    def step(self,target,dt):
        for name,current in self.positions.items():
            distance=target[name]-current
            desired=copysign(min(self.speed,sqrt(2*self.acceleration*abs(distance))),distance) if distance else 0.0
            previous=self.velocity[name]
            velocity=previous+max(-self.acceleration*dt,min(self.acceleration*dt,desired-previous))
            delta=velocity*dt
            if distance*delta>=0 and abs(delta)>=abs(distance):
                self.positions[name]=target[name];self.velocity[name]=0.0
            else:
                self.positions[name]=current+delta;self.velocity[name]=velocity
        return dict(self.positions)

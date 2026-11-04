"""功能：正常失能前限速回零，确认实际反馈后关闭力矩。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
from math import ceil
from time import sleep
from ..safety import JOINTS
from .joint_trajectory import JointTrajectory

class SlowZeroRelease:
    def __init__(self,calibration,speed,feedback=None):
        self.calibration=calibration;self.speed=speed;self.feedback=feedback

    def run(self,bus):
        zero=dict.fromkeys(JOINTS,0.0)
        self.calibration.limits.validate(zero)
        start=self.calibration.angles(bus.sync_read('Present_Position',normalize=False))
        count=max(1,ceil((max(abs(v) for v in start.values())/self.speed+2*self.speed/.3+1)*30))
        trajectory=JointTrajectory(start,self.speed)
        previous_ticks=None
        measured=start
        for index in range(1,count+1):
            target=trajectory.step(zero,1/30)
            ticks=self.calibration.ticks(target)
            if ticks!=previous_ticks:
                bus.sync_write('Goal_Position',ticks,normalize=False);previous_ticks=ticks
            sleep(1/30)
            measured=self.calibration.angles(bus.sync_read('Present_Position',normalize=False))
            if self.feedback:self.feedback(measured)
            if max(abs(v) for v in target.values())<1e-8:break
        # 轨迹下发结束后等实际电机收敛，不能把命令为零当成已回零。
        for _ in range(90):
            if max(abs(v) for v in measured.values())<.025:
                return {'zero_reached':True,'joint_positions':measured}
            sleep(1/30)
            measured=self.calibration.angles(bus.sync_read('Present_Position',normalize=False))
            if self.feedback:self.feedback(measured)
        raise RuntimeError('回零未到位，电机反馈未跟随零位目标')

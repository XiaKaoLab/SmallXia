"""功能：正常失能前限速返回本次运行起始姿态，确认实际反馈后关闭力矩。
Created on 2026-11-04; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""
from math import ceil
from time import sleep
from ..safety import JOINTS
from .joint_trajectory import JointTrajectory
from .joint_pid import JointPID

class SlowZeroRelease:
    def __init__(self,calibration,speed,feedback=None,target=None,pid_compensation=None,software_pid_enabled=True):
        self.calibration=calibration;self.speed=speed;self.feedback=feedback
        self.pid_compensation=pid_compensation
        self.software_pid_enabled=software_pid_enabled
        self.target=dict(target) if target is not None else dict.fromkeys(JOINTS,0.0)

    def run(self,bus):
        zero=self.target
        self.calibration.ticks(zero)
        start=self.calibration.angles(bus.sync_read('Present_Position',normalize=False))
        count=max(1,ceil((max(abs(start[n]-zero[n]) for n in JOINTS)/self.speed+2*self.speed/.3+1)*30))
        trajectory=JointTrajectory(start,self.speed)
        pid=JointPID(start,self.speed,compensation=self.pid_compensation) if self.software_pid_enabled else None
        if pid:pid.target(zero)
        previous_ticks=None
        measured=start
        for index in range(1,count+1):
            reference=trajectory.step(zero,1/30)
            target=pid.step(reference,measured,1/30,self.speed) if pid else reference
            target={n:max(min(start[n],zero[n]),min(max(start[n],zero[n]),v)) for n,v in target.items()}
            ticks=self.calibration.ticks(target)
            if ticks!=previous_ticks:
                bus.sync_write('Goal_Position',ticks,normalize=False);previous_ticks=ticks
            sleep(1/30)
            measured=self.calibration.angles(bus.sync_read('Present_Position',normalize=False))
            if self.feedback:self.feedback(measured)
            if max(abs(target[n]-zero[n]) for n in JOINTS)<JointPID.tick:break
        # 轨迹下发结束后等实际电机收敛，不能把命令为零当成已回零。
        for _ in range(90):
            if max(abs(measured[n]-zero[n]) for n in JOINTS)<.025:
                return {'zero_reached':True,'start_reached':True,'reference':'run_start','target_joint_positions':dict(zero),'joint_positions':measured}
            sleep(1/30)
            measured=self.calibration.angles(bus.sync_read('Present_Position',normalize=False))
            if self.feedback:self.feedback(measured)
        raise RuntimeError('未返回起始位置，电机反馈未跟随回位目标')

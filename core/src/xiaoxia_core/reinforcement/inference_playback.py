"""按物理时间控制推理画面节奏，计算较慢时不通过连续跳帧追赶。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from time import monotonic, sleep


class InferencePlayback:
    def __init__(self, speed=1.0):
        self.speed = speed

    def wait_step(self, started, simulated_seconds):
        if self.speed == 0:
            return
        remaining = simulated_seconds / self.speed - (monotonic() - started)
        if remaining > 0:
            sleep(remaining)

    def pause_episode(self):
        if self.speed:
            sleep(.3)

"""功能：按实际位置变化识别运动停滞，不限制正常运动的总时长。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from time import monotonic


class MotionProgress:
    def __init__(self, message='关节没有接近目标，请检查机械臂反馈', *, clock=monotonic):
        self.clock = clock
        self.message = message
        self.best = None
        self.changed_at = clock()

    def update(self, current, target, tolerance=.025):
        error = max(abs(current[name] - value) for name, value in target.items())
        now = self.clock()
        if error <= tolerance:
            self.best, self.changed_at = error, now
            return
        if self.best is None or error < self.best - .0015:
            self.best, self.changed_at = error, now
        elif now - self.changed_at > 4:
            raise RuntimeError(self.message)

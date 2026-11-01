"""按实际观测管理抓取阶段、闭爪条件与失抓恢复；不求解 IK 或代替学习网络。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import numpy as np


class PickupPhases:
    names = ('search', 'approach', 'align', 'close', 'lift', 'hold', 'recover')

    def __init__(self):
        self.name = 'search'
        self.lost_steps = 0
        self.visited = {'search'}

    def update(self, *, visible, delta, orientation_error, contact, lifted, gripper):
        both = contact['both_jaws']
        self.lost_steps = 0 if both else self.lost_steps + 1
        previous = self.name
        if self.name == 'search' and visible:
            self.name = 'approach'
        if self.name == 'approach' and np.linalg.norm(delta[:2]) < .012 and orientation_error < .2:
            self.name = 'align'
        if self.name == 'align' and np.linalg.norm(delta) < .008 and orientation_error < .15:
            self.name = 'close'
        if self.name == 'close':
            if both:
                self.name = 'lift'
            elif gripper < -.08:
                self.name = 'recover'
        elif self.name in ('lift', 'hold'):
            if self.lost_steps >= 3:
                self.name = 'recover'
            elif both and lifted >= .05:
                self.name = 'hold'
        elif self.name == 'recover' and gripper > .6:
            self.name = 'approach'
        first = self.name not in self.visited
        self.visited.add(self.name)
        return .25 if first and self.name in ('align', 'close', 'lift', 'hold') else 0.

    def mask(self, action):
        masked = np.asarray(action, dtype=np.float32).copy()
        if self.name not in ('close', 'lift', 'hold'):
            masked[5] = max(0., masked[5])
        return masked

    def one_hot(self):
        return [float(name == self.name) for name in self.names]

"""由中心区域逐级扩展至全工作区，以全通过验证晋级，阶段均衡采样。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from collections import defaultdict
import numpy as np


class PickupCurriculum:
    widths = (.2, .55, 1.)

    def __init__(self):
        self.level = 0

    def configure(self, environments):
        for env in environments:
            env.curriculum_level = self.level

    def promote(self, result):
        if result['successes'] == result['rounds'] and self.level < 2:
            self.level += 1
            return True
        return False

    @staticmethod
    def sample(rows, count, rng):
        groups = defaultdict(list)
        for row in rows:
            groups[int(np.argmax(row[0]['observation.state'][18:25]))].append(row)
        if not groups:
            raise ValueError('阶段回放没有样本')
        phases = list(groups)
        rng.shuffle(phases)
        return [rng.choice(groups[phases[index % len(phases)]]) for index in range(count)]

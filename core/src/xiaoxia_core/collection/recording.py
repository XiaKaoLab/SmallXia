"""将有限时长录制转换为目标帧数，复用采集队列和数据集写入流程。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from math import ceil, isfinite


class RecordingPlan:
    def __init__(self, duration_s, fps):
        if type(duration_s) not in (int, float) or not isfinite(duration_s) or not 1 <= duration_s <= 3600:
            raise ValueError('录制时长需要 1–3600 秒的有限数值')
        self.duration_s = float(duration_s)
        self.target_frames = ceil(self.duration_s * fps)
        if self.target_frames < 2:
            raise ValueError('一段录制至少两帧，请增加时长或帧率')

    def payload(self, action=None):
        return {'duration_s': self.duration_s, **({'action': action} if action is not None else {})}

"""按物理时间控制推理画面节奏，计算较慢时不通过连续跳帧追赶。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
from time import monotonic, sleep


class InferencePlayback:
    def __init__(self, speed=1.0, worker=None):
        self.speed = speed
        self.worker = worker
        self.requested_pause = False

    def checkpoint(self):
        if self.worker is None:
            return
        def requested():
            try:
                data = json.loads((self.worker.directory / 'playback-control.json').read_text(encoding='utf-8'))
                self.requested_pause = data.get('paused') is True
            except (OSError, ValueError):
                pass  # 暂时读取失败时保留已有暂停意图，不擅自继续。
            return self.requested_pause
        if not requested():
            return
        self.worker.progress(paused=True, phase='paused')
        acknowledged = monotonic()
        while requested():
            if monotonic() - acknowledged >= .5:
                self.worker.progress(paused=True, phase='paused')
                acknowledged = monotonic()
            sleep(.005)
        self.worker.progress(paused=False, phase='inferencing')

    def wait(self, seconds):
        remaining = seconds
        while remaining > 0:
            self.checkpoint()
            started = monotonic()
            sleep(min(.005, remaining))
            remaining -= monotonic() - started
        self.checkpoint()

    def wait_step(self, started, simulated_seconds):
        if self.speed:
            self.wait(max(0., simulated_seconds / self.speed - (monotonic() - started)))
        else:
            self.checkpoint()

    def pause_episode(self):
        if self.speed:
            self.wait(.3)

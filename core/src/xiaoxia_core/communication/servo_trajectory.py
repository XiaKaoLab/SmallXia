"""功能：一次发送绝对终点，使用 STS3215 内部速度与加速度轨迹，重复目标不重启。
Created on 2026-11-08; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""
from math import floor, isfinite, pi


class ServoTrajectory:
    def __init__(self, bus, calibration, acceleration=.3):
        self.bus, self.calibration = bus, calibration
        self.phase = bus.sync_read('Phase', normalize=False)
        self.backup = {name: bus.sync_read(name, normalize=False) for name in ('Acceleration', 'Goal_Velocity')}
        self.acceleration = max(1, min(254, floor(acceleration / (8.7 * pi / 180))))
        self.previous = None
        self.goal_writes = 0
        self.speed_registers = {}

    def send(self, positions, speed):
        if not isfinite(speed) or speed <= 0:
            raise ValueError('舵机轨迹速度必须为有限正数')
        ticks = self.calibration.ticks(positions)
        # Phase BIT2 selects RPM units. Fine units still have coarse hardware precision.
        velocities = {}
        for name, phase in self.phase.items():
            unit = .0146 if phase & 4 else .732
            quantum = 50 if phase & 4 else 1
            raw = floor(speed * 60 / (2 * pi) / unit / quantum) * quantum
            if raw < quantum:
                raise ValueError('请求速度低于舵机内部速度分辨率，请使用软件轨迹模式')
            velocities[name] = min(32767, raw)
        key = (tuple(ticks.items()), tuple(velocities.items()))
        if key == self.previous:
            return
        self.bus.sync_write('Acceleration', dict.fromkeys(ticks, self.acceleration), normalize=False)
        self.bus.sync_write('Goal_Velocity', velocities, normalize=False)
        if self.bus.sync_read('Goal_Velocity', normalize=False) != velocities:
            raise RuntimeError('舵机速度参数读回不一致')
        if self.bus.sync_read('Acceleration', normalize=False) != dict.fromkeys(ticks, self.acceleration):
            raise RuntimeError('舵机加速度参数读回不一致')
        self.bus.sync_write('Goal_Position', ticks, normalize=False)
        self.previous = key
        self.goal_writes += 1
        self.speed_registers = velocities

    def restore(self):
        for name, values in self.backup.items():
            self.bus.sync_write(name, values, normalize=False)
            if self.bus.sync_read(name, normalize=False) != values:
                raise RuntimeError('舵机轨迹临时参数恢复失败：' + name)

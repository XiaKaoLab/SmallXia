"""复用与 EEPROM 匹配的 LeRobot 校准；缺失时同时采集六轴手动运动极限，不发送运动目标。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from dataclasses import asdict
from hashlib import sha256
import json
from math import pi
from pathlib import Path
from time import sleep, time

from ..imitation.api_jobs import atomic_json
from ..safety import JOINTS


class OfficialCalibrationStore:
    @staticmethod
    def validate(raw):
        if set(raw) != set(JOINTS):
            raise ValueError('官方校准必须包含六个关节')
        for index, name in enumerate(JOINTS, 1):
            row = raw[name]
            if any(type(row.get(key)) is not int for key in ('id', 'drive_mode', 'homing_offset', 'range_min', 'range_max')):
                raise ValueError(f'{name} 校准字段必须是整数')
            if row['id'] != index or row['drive_mode'] != 0 or not -2047 <= row['homing_offset'] <= 2047:
                raise ValueError(f'{name} ID、方向或偏移不匹配 STS3215')
            if not 0 <= row['range_min'] < row['range_max'] <= 4095:
                raise ValueError(f'{name} 最小、最大位置无效')
            if name != 'wrist_roll' and row['range_min'] == 0 and row['range_max'] == 4095:
                raise ValueError(f'{name} 仍为出厂全量程，需采集实际机械行程')
        return raw

    @staticmethod
    def root():
        from lerobot.utils.constants import HF_LEROBOT_CALIBRATION
        return Path(HF_LEROBOT_CALIBRATION) / 'robots' / 'so_follower'

    @classmethod
    def reuse(cls, device, port):
        cls.validate(device)
        root = cls.root()
        for folder in (root, root.parent / 'so100_follower'):
            for path in sorted(folder.glob('*.json')):
                try:
                    candidate = cls.validate(json.loads(path.read_text(encoding='utf-8')))
                    if candidate == device:
                        return str(path), 'matching_file'
                except (OSError, ValueError, TypeError, KeyError):
                    continue
        # EEPROM 本身也保存 LeRobot 的偏移和范围。仅导出当前数据，绝不将旧文件覆盖到设备。
        digest = sha256(json.dumps(device, sort_keys=True).encode()).hexdigest()[:12]
        path = root / f'xiaoxia_{port}_{digest}.json'
        root.mkdir(parents=True, exist_ok=True)
        atomic_json(path, device)
        return str(path), 'device_eeprom'


class OfficialUrdfMap:
    """新校准模型：五轴按官方 DEGREES 转弧度；夹爪开合比例映射到模型 0..upper。"""
    def __init__(self, calibration, limits):
        self.calibration = OfficialCalibrationStore.validate(calibration)
        self.limits = limits

    def angles(self, ticks):
        if set(ticks) != set(JOINTS) or any(type(v) is not int or not 0 <= v <= 4095 for v in ticks.values()):
            raise ValueError('需要完整的六轴单圈原始编码器计数')
        result = {}
        for name in JOINTS:
            row = self.calibration[name]
            if name == 'gripper':
                fraction = (ticks[name] - row['range_min']) / (row['range_max'] - row['range_min'])
                result[name] = min(1, max(0, fraction)) * self.limits.joints[name].upper
            else:
                result[name] = (ticks[name] - (row['range_min'] + row['range_max']) / 2) * 2 * pi / 4095
        return result


class GuidedArmCalibration:
    def __init__(self, bus, directory, publish):
        self.bus, self.directory, self.publish = bus, directory, publish

    def active(self):
        return not (self.directory / 'stop').exists() and time() - (self.directory / 'lease').stat().st_mtime < 10

    def command(self, stage, index):
        path = self.directory / 'calibration-command.json'
        if not path.exists():
            return False
        try:
            command = json.loads(path.read_text(encoding='utf-8'))
            return command == {'stage': stage, 'index': index}
        finally:
            path.unlink(missing_ok=True)

    def ensure(self, *, force=False):
        self.require_manual_mode()
        original = {name: asdict(value) for name, value in self.bus.read_calibration().items()}
        try:
            if force:
                raise ValueError("已选择重新校准，不复用原行程数据")
            path, source = OfficialCalibrationStore.reuse(original, self.bus.port)
            return original, path, source
        except ValueError as error:
            reason = str(error)
        changed = False
        committed = False
        try:
            while self.active():
                self.require_manual_mode()
                self.publish(status='waiting_center', calibration_stage='center', joint_index=-1,
                             instruction=f'{reason}。手动将各关节放在行程中部，再点击“记录中位并检查行程”。')
                if self.command('center', -1):
                    changed = True
                    self.bus.allow_calibration_writes = True
                    atomic_json(self.directory / "calibration-before.json", original)
                    offsets = self.bus.set_half_turn_homings()
                    break
                sleep(.1)
            else:
                raise InterruptedError('已取消校准')
            lows = highs = None
            issue = ''
            while self.active():
                self.require_manual_mode()
                ticks = {name: int(value) for name, value in self.bus.sync_read('Present_Position', normalize=False).items()}
                if set(ticks) != set(JOINTS) or any(not 0 <= value <= 4095 for value in ticks.values()):
                    raise ValueError('编码器跨圈，请重新摆正中位再校准')
                lows = dict(ticks) if lows is None else {name: min(lows[name], ticks[name]) for name in JOINTS}
                highs = dict(ticks) if highs is None else {name: max(highs[name], ticks[name]) for name in JOINTS}
                ranges = {name: {'current': ticks[name], 'min': lows[name], 'max': highs[name],
                                'mid': (lows[name] + highs[name]) / 2} for name in JOINTS}
                self.publish(status='checking_range', calibration_stage='range', joint_index=-1,
                    joint_ranges=ranges,
                    instruction=issue or '同时采集全部六轴。手动活动各关节至两个端点，夹爪完全闭合并张开；六行滑杆实时显示当前、最小、最大及中值，全部完成后一次保存。腕部旋转仍按官方全周范围。')
                if self.command('range', -1):
                    missing = [name for name in JOINTS if name != 'wrist_roll' and highs[name] - lows[name] < 100]
                    if missing:
                        issue = '以下关节采集行程不足，请继续活动后保存：' + '、'.join(missing)
                    else:
                        raw = {name: dict(id=index + 1, drive_mode=0, homing_offset=int(offsets[name]),
                            range_min=0 if name == 'wrist_roll' else lows[name],
                            range_max=4095 if name == 'wrist_roll' else highs[name]) for index, name in enumerate(JOINTS)}
                        break
                sleep(.05)
            else:
                raise InterruptedError('已取消校准')
            OfficialCalibrationStore.validate(raw)
            from lerobot.motors import MotorCalibration
            self.require_manual_mode()
            self.bus.write_calibration({name: MotorCalibration(**row) for name, row in raw.items()})
            readback = {name: asdict(value) for name, value in self.bus.read_calibration().items()}
            if readback != raw:
                raise ValueError('校准写入后读回不一致')
            path, _ = OfficialCalibrationStore.reuse(raw, self.bus.port)
            committed = True
            self.bus.allow_calibration_writes = False
            return raw, path, 'guided_range_check'
        finally:
            if changed and not committed:
                from lerobot.motors import MotorCalibration
                self.require_manual_mode()
                self.bus.write_calibration({name: MotorCalibration(**row) for name, row in original.items()})
                restored = {name: asdict(value) for name, value in self.bus.read_calibration().items()}
                if restored != original:
                    raise RuntimeError('校准取消后恢复 EEPROM 失败，请检查设备')
            self.bus.allow_calibration_writes = False

    def require_manual_mode(self):
        if any(self.bus.sync_read('Torque_Enable', normalize=False).values()):
            raise ValueError('请先安全支撑机械臂并关闭力矩；校准不自动改变力矩或驱动关节')
        if any(self.bus.read('Operating_Mode', name, normalize=False) != 0 for name in JOINTS):
            raise ValueError('六轴必须已处于位置模式，校准不自动切换模式')

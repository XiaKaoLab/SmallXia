"""记录当前姿态的显示对齐关系，只读跟随六轴编码器，不改写电机校准。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from time import sleep, time
from uuid import uuid4

from ..imitation.api_jobs import atomic_json, identifier
from ..safety import JOINTS


class DisplayAlignment:
    root = Path(__file__).resolve().parents[3] / 'data/display_alignment'

    @classmethod
    def start(cls, port, reference, directions):
        from math import isfinite
        if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
            raise ValueError('请选择实际 COM 口')
        if set(reference) != set(JOINTS) or not all(isinstance(v, (int, float)) and isfinite(v) for v in reference.values()):
            raise ValueError('需要完整的当前仿真姿态')
        if set(directions) != set(JOINTS) or any(v not in (-1, 1) for v in directions.values()):
            raise ValueError('需要六轴编码器方向')
        from ..safety import JointLimits
        JointLimits.from_urdf(Path(__file__).resolve().parents[4] / 'table/public/robots/so101/so101_new_calib.urdf').validate(reference)
        cls.root.mkdir(parents=True, exist_ok=True)
        pending = []
        for existing in cls.root.glob('*/request.json'):
            try:
                old = json.loads(existing.read_text(encoding='utf-8'))
                if old.get('port') == port:
                    (existing.parent / 'stop').touch()
                    pending.append(existing.parent)
            except (OSError, ValueError):
                continue
        deadline = time() + 2
        while pending:
            remaining = []
            for previous in pending:
                try:
                    state = json.loads((previous / 'state.json').read_text(encoding='utf-8'))
                    if state['status'] not in ('failed', 'stopped'):
                        remaining.append(previous)
                except (OSError, ValueError):
                    remaining.append(previous)
            if not remaining:
                break
            if time() >= deadline:
                raise ValueError('上一显示对齐仍在释放串口，请稍后重新运行')
            pending = remaining
            sleep(.05)
        directory = cls.root / uuid4().hex
        directory.mkdir()
        atomic_json(directory / 'request.json', {'port': port, 'reference': reference, 'directions': directions})
        atomic_json(directory / 'state.json', {'status': 'connecting', 'port': port})
        (directory / 'lease').touch()
        with (directory / 'worker.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-u', '-m', __name__, directory.name], stdout=log, stderr=log,
                env={**os.environ, 'USE_TF': '0'}, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return {'id': directory.name, 'port': port, 'status': 'connecting', 'reference': reference, 'display_only': True}

    @classmethod
    def stream(cls, session_id, emit):
        directory = cls.root / identifier(session_id)
        if not directory.is_dir():
            raise ValueError('显示对齐会话不存在')
        previous = None
        started = time()
        try:
            while True:
                (directory / 'lease').touch()
                try:
                    state = json.loads((directory / 'state.json').read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    sleep(.05)
                    continue
                if state['status'] == 'connecting' and time() - started > 60:
                    state = {**state, 'status': 'failed', 'error': '等待串口连接超过 60 秒，请检查日志后重新运行'}
                if state != previous:
                    emit({'type': 'alignment', 'data': state})
                    previous = state
                if state['status'] in ('failed', 'stopped'):
                    break
                sleep(.05)
        finally:
            (directory / 'stop').touch()
        emit({'type': 'completed'})

    @classmethod
    def stop(cls, session_id):
        directory = cls.root / identifier(session_id)
        if not directory.is_dir():
            raise ValueError('显示对齐会话不存在')
        (directory / 'stop').touch()
        return {'stopping': True}

    @classmethod
    def run(cls, session_id):
        from dataclasses import asdict
        from math import pi
        from lerobot.motors import Motor, MotorNormMode
        from lerobot.motors.feetech import FeetechMotorsBus

        class ReadOnlyBus(FeetechMotorsBus):
            def write(self, *args, **kwargs): raise RuntimeError('显示对齐禁止写入')
            def sync_write(self, *args, **kwargs): raise RuntimeError('显示对齐禁止写入')
            def enable_torque(self, *args, **kwargs): raise RuntimeError('显示对齐禁止使能力矩')
            def disable_torque(self, *args, **kwargs): raise RuntimeError('显示对齐禁止改写力矩')

        directory = cls.root / identifier(session_id)
        request = json.loads((directory / 'request.json').read_text(encoding='utf-8'))
        bus = ReadOnlyBus(request['port'], {name: Motor(i, 'sts3215', MotorNormMode.DEGREES) for i, name in enumerate(JOINTS, 1)})
        state = {'status': 'connecting', 'port': request['port'], 'display_only': True}
        try:
            if (directory / 'stop').exists() or time() - (directory / 'lease').stat().st_mtime >= 10:
                state['status'] = 'stopped'
                return
            bus.connect()
            bus.set_timeout(150)
            if any(bus.sync_read('Torque_Enable', normalize=False).values()):
                raise ValueError('显示对齐要求机械臂已安全支撑且力矩关闭；本工具不改变力矩')
            baseline = bus.sync_read('Present_Position', normalize=False)
            calibration = bus.read_calibration()
            atomic_json(directory / 'alignment.json', {**request, 'baseline_ticks': baseline,
                'device_calibration': {name: asdict(value) for name, value in calibration.items()},
                'verified_for_motion': False})
            while not (directory / 'stop').exists() and time() - (directory / 'lease').stat().st_mtime < 10:
                ticks = bus.sync_read('Present_Position', normalize=False)
                if any(bus.sync_read('Torque_Enable', normalize=False).values()):
                    raise ValueError('检测到力矩已开启，结束只读显示对齐')
                angles = {name: request['reference'][name] + request['directions'][name]
                    * (((ticks[name] - baseline[name] + 2047.5) % 4095) - 2047.5) * 2 * pi / 4095 for name in JOINTS}
                state.update(status='following', timestamp=time(), joint_positions=angles, ticks=ticks,
                    outside_device_calibration=[name for name in JOINTS if not calibration[name].range_min <= ticks[name] <= calibration[name].range_max])
                atomic_json(directory / 'state.json', state)
                sleep(.05)
            state['status'] = 'stopped'
        except Exception as error:
            state.update(status='failed', error=str(error))
        finally:
            if bus.is_connected:
                bus.disconnect(disable_torque=False)
            state['disconnected'] = not bus.is_connected
            atomic_json(directory / 'state.json', state)


if __name__ == '__main__':
    try:
        DisplayAlignment.run(sys.argv[1])
    except Exception as error:
        directory = DisplayAlignment.root / identifier(sys.argv[1])
        atomic_json(directory / 'state.json', {'status': 'failed', 'error': str(error), 'display_only': True})
        raise

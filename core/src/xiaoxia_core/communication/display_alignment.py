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
    def start(cls, port, reference, directions, *, source_alignment=None):
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
        atomic_json(directory / 'request.json', {'port': port, 'reference': reference, 'directions': directions,
            'mode': 'mapping' if source_alignment else 'alignment', 'source_alignment': source_alignment})
        atomic_json(directory / 'state.json', {'status': 'connecting', 'port': port})
        (directory / 'lease').touch()
        with (directory / 'worker.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-u', '-m', __name__, directory.name], stdout=log, stderr=log,
                env={**os.environ, 'USE_TF': '0'}, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return {'id': directory.name, 'port': port, 'status': 'connecting', 'reference': reference, 'display_only': True, 'mode': 'mapping' if source_alignment else 'alignment'}

    @classmethod
    def start_mapping(cls, port):
        candidates = []
        for path in cls.root.glob('*/alignment.json'):
            try:
                config = json.loads(path.read_text(encoding='utf-8'))
                if config.get('port') == port and config.get('mode', 'alignment') == 'alignment':
                    candidates.append((path.stat().st_mtime_ns, path.parent.name, config))
            except (OSError, ValueError):
                continue
        if not candidates:
            raise ValueError('此串口没有显示对齐记录，请先运行校准机械臂，确认起点和六轴方向')
        _, identity, config = max(candidates, key=lambda item: item[0])
        return cls.start(port, config['reference'], config['directions'], source_alignment=identity)

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
            route = None
            if request.get('source_alignment'):
                source = cls.root / identifier(request['source_alignment']) / 'alignment.json'
                saved = json.loads(source.read_text(encoding='utf-8'))
                if saved['port'] != request['port'] or saved['device_calibration'] != {name: asdict(value) for name, value in calibration.items()}:
                    raise ValueError('设备校准快照已变化，请重新做显示对齐')
                baseline = saved['baseline_ticks']
                from ..safety import JointLimits
                from .motion_routes import MotionRouteClient
                from ..contracts import Action
                limits = JointLimits.from_urdf(Path(__file__).resolve().parents[4] / 'table/public/robots/so101/so101_new_calib.urdf')
                route = MotionRouteClient('http://127.0.0.1:8766', 'table', limits,
                    token=os.environ['XIAOXIA_MOTION_TOKEN'], timeout=1)
                model = route._request('GET', '/state')
                if model.get('physical') is not False or model.get('source') != 'display_target':
                    raise ValueError('映射目标必须是 table 仿真显示模型')
                if (model.get('playback') or {}).get('status') in ('running', 'paused'):
                    raise ValueError('请先停止录制播放，再开始真机映射')
                route.connect()
                state.update(mode='mapping', source_alignment=request['source_alignment'], model_target='table', source_physical=True)

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
                if route is not None:
                    constrained = {name: max(limits.joints[name].lower, min(limits.joints[name].upper, angle)) for name, angle in angles.items()}
                    route.send_action(Action(constrained))
                    receipt = route.last_receipt
                    state.update(applied_joint_positions=receipt['applied_joint_positions'],
                        model_limited=bool(receipt.get('limited')) or constrained != angles,
                        limit_reason=receipt.get('limit_reason') or ('关节限位' if constrained != angles else ''))
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

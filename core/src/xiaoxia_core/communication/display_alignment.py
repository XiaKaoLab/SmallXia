"""复用官方校准跟随实机，缺失时引导逐轴检查行程；仅校准写入，无运动目标。
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
    def start(cls, port, *, mapping=False, recalibrate=False):
        if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
            raise ValueError('请选择实际 COM 口')
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
                    if state['status'] not in ('failed', 'stopped', 'saved'):
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
        atomic_json(directory / 'request.json', {'port': port, 'mode': 'mapping' if mapping else 'alignment', 'recalibrate': bool(recalibrate)})
        atomic_json(directory / 'state.json', {'status': 'connecting', 'port': port})
        (directory / 'lease').touch()
        with (directory / 'worker.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-u', '-m', __name__, directory.name], stdout=log, stderr=log,
                env={**os.environ, 'USE_TF': '0', 'PYTHONPATH': str(Path(__file__).resolve().parents[1].parent) + os.pathsep + os.environ.get('PYTHONPATH', '')}, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return {'id': directory.name, 'port': port, 'status': 'connecting', 'display_only': True, 'mode': 'mapping' if mapping else 'alignment'}

    @classmethod
    def start_mapping(cls, port):
        return cls.start(port, mapping=True)

    @classmethod
    def calibration_action(cls, session_id, stage, index):
        if stage not in ('center', 'range') or type(index) is not int or not -1 <= index <= 5:
            raise ValueError('无效的校准步骤')
        directory = cls.root / identifier(session_id)
        state = json.loads((directory / 'state.json').read_text(encoding='utf-8'))
        if state.get('status') not in ('waiting_center', 'checking_range') or state.get('calibration_stage') != stage or state.get('joint_index') != index:
            raise ValueError('校准步骤已变化，请等待最新状态')
        if stage == 'range':
            suspicious = [name for name, values in state.get('joint_ranges', {}).items()
                          if name != 'wrist_roll' and values['max'] - values['min'] >= 3800]
            if suspicious:
                raise ValueError('采集范围疑似跨圈，请停止并在行程中部重新校准：' + '、'.join(suspicious))
        # 独占创建防止快速双击跳过关节；请求不自动重试。
        temporary = directory / f'command-{uuid4().hex}.json'
        atomic_json(temporary, {'stage': stage, 'index': index})
        try:
            os.link(temporary, directory / 'calibration-command.json')
        finally:
            temporary.unlink(missing_ok=True)
        return {'accepted': True}

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
                    atomic_json(directory / 'state.json', state)
                if state != previous:
                    emit({'type': 'alignment', 'data': state})
                    previous = state
                if state['status'] in ('failed', 'stopped', 'saved'):
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
        from .official_calibration import GuidedArmCalibration, OfficialUrdfMap
        from lerobot.motors import Motor, MotorNormMode
        from lerobot.motors.feetech import FeetechMotorsBus

        class CalibrationOnlyBus(FeetechMotorsBus):
            allow_calibration_writes = False
            calibration_write_count = 0
            def write(self, data_name, *args, **kwargs):
                if not self.allow_calibration_writes or data_name not in ('Homing_Offset', 'Min_Position_Limit', 'Max_Position_Limit'):
                    raise RuntimeError('仅允许校准参数写入，禁止运动和力矩写入')
                self.calibration_write_count += 1
                return super().write(data_name, *args, **kwargs)
            def sync_write(self, *args, **kwargs): raise RuntimeError('显示对齐禁止写入')
            def enable_torque(self, *args, **kwargs): raise RuntimeError('显示对齐禁止使能力矩')
            def disable_torque(self, *args, **kwargs): raise RuntimeError('显示对齐禁止改写力矩')

        directory = cls.root / identifier(session_id)
        request = json.loads((directory / 'request.json').read_text(encoding='utf-8'))
        bus = CalibrationOnlyBus(request['port'], {name: Motor(i, 'sts3215', MotorNormMode.DEGREES) for i, name in enumerate(JOINTS, 1)})
        state = {'status': 'connecting', 'port': request['port'], 'display_only': True}
        try:
            if (directory / 'stop').exists() or time() - (directory / 'lease').stat().st_mtime >= 10:
                state['status'] = 'stopped'
                return
            bus.connect()
            bus.set_timeout(150)
            if any(bus.sync_read('Torque_Enable', normalize=False).values()):
                raise ValueError('显示对齐要求机械臂已安全支撑且力矩关闭；本工具不改变力矩')
            def publish(**values):
                state.update(values, timestamp=time())
                atomic_json(directory / 'state.json', state)
            raw_calibration, calibration_path, calibration_source = GuidedArmCalibration(bus, directory, publish).ensure(force=request.get('recalibrate', False))
            if calibration_source == 'guided_range_check':
                state.update(status='saved', calibration_path=calibration_path, calibration_source=calibration_source,
                             instruction='校准已保存', timestamp=time())
                return
            calibration = bus.read_calibration()
            from ..safety import JointLimits
            limits = JointLimits.from_urdf(Path(__file__).resolve().parents[4] / 'table/public/robots/so100/so100_mid_calib.urdf')
            route = None
            if request['mode'] == 'mapping':
                from .motion_routes import MotionRouteClient
                from ..contracts import Action
                route = MotionRouteClient('http://127.0.0.1:8766', 'table', limits,
                    token=os.environ['XIAOXIA_MOTION_TOKEN'], timeout=1)
                model = route._request('GET', '/state')
                if model.get('physical') is not False or model.get('source') != 'display_target':
                    raise ValueError('映射目标必须是 table 仿真显示模型')
                if (model.get('playback') or {}).get('status') in ('running', 'paused'):
                    raise ValueError('请先停止录制播放，再开始真机映射')
                route.connect()
                state.update(mode='mapping', model_target='table', source_physical=True)

            joint_map = OfficialUrdfMap(raw_calibration, limits)
            state.update(angle_basis='lerobot_degrees_to_urdf_v1', input_unit='encoder_ticks', output_unit='rad',
                gripper_unit='percent_to_urdf_rad', geometry_verified=False,
                calibration_source=calibration_source, calibration_path=calibration_path,
                instruction='已复用匹配的官方校准；五轴按行程中点转弧度，夹爪按开合比例转换。')
            atomic_json(directory / 'alignment.json', {**request, 'angle_basis': state['angle_basis'],
                'calibration_path': calibration_path, 'calibration_source': calibration_source,
                'device_calibration': raw_calibration, 'geometry_verified': False, 'verified_for_motion': False})
            while not (directory / 'stop').exists() and time() - (directory / 'lease').stat().st_mtime < 10:
                ticks = bus.sync_read('Present_Position', normalize=False)
                if any(bus.sync_read('Torque_Enable', normalize=False).values()):
                    raise ValueError('检测到力矩已开启，结束只读显示对齐')
                angles = joint_map.angles(ticks)
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
            state['calibration_write_count'] = bus.calibration_write_count
            state['disconnected'] = not bus.is_connected
            atomic_json(directory / 'state.json', state)


if __name__ == '__main__':
    try:
        DisplayAlignment.run(sys.argv[1])
    except Exception as error:
        directory = DisplayAlignment.root / identifier(sys.argv[1])
        atomic_json(directory / 'state.json', {'status': 'failed', 'error': str(error), 'display_only': True})
        raise

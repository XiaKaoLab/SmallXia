"""功能：固定单轴往返对照软件外环，保存原始舵机反馈与真实相机录像，不运行策略。
Created on 2026-11-08; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""
import argparse
import base64
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Event, Thread

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE / 'src'))
from xiaoxia_core.environment import EnvironmentSettings
from xiaoxia_core.blocks.workflow import BlockWorkflow
from xiaoxia_core.imitation.workflows import HardwareWorkflow
from xiaoxia_core.contracts import Action


class CameraRecorder:
    def __init__(self, directory, source, phase):
        self.directory, self.source, self.phase = directory, source, phase
        self.stop, self.ready = Event(), Event()
        self.result = {'camera_id': source, 'physical': True, 'frames': 0}
        self.thread = Thread(target=self.run, daemon=True)

    def run(self):
        import cv2
        import numpy as np
        writer = None
        first_time = None; last_image = None; next_frame_time = .1
        self.result['video_fps'] = 10; self.result['video_timing'] = 'hold_last_frame_at_capture_timestamps'
        self.result['video_frames'] = 0
        try:
            with (self.directory / 'camera-frames.jsonl').open('w', encoding='utf8') as stamps:
                while not self.stop.is_set():
                    began = time.monotonic()
                    frame = BlockWorkflow.http('cameras/' + self.source + '/frame')
                    if frame.get('physical') is not True: raise RuntimeError('相机来源不是实拍')
                    image = cv2.imdecode(np.frombuffer(base64.b64decode(frame['image_base64']), np.uint8), cv2.IMREAD_COLOR)
                    if image is None: raise RuntimeError('相机解码失败')
                    if writer is None:
                        writer = cv2.VideoWriter(str(self.directory / 'camera.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), 10, (image.shape[1], image.shape[0]))
                        if not writer.isOpened(): raise RuntimeError('录像文件无法打开')
                    received = time.monotonic()
                    if first_time is None:
                        first_time = received; writer.write(image); self.result['video_frames'] += 1
                    else:
                        while next_frame_time <= received - first_time:
                            writer.write(last_image); self.result['video_frames'] += 1; next_frame_time += .1
                    last_image = image
                    stamps.write(json.dumps({'received_at_ns': time.time_ns(), 'camera_timestamp_ns': frame.get('timestamp_ns'), 'sequence': frame.get('sequence'), 'phase': dict(self.phase)}, ensure_ascii=False) + '\n')
                    self.result['frames'] += 1; self.ready.set()
                    self.stop.wait(max(0, .1 - (time.monotonic() - began)))
        except Exception as error: self.result['error'] = str(error); self.ready.set()
        finally:
            if writer: writer.release()

    def start(self):
        self.thread.start(); self.ready.wait(5)

    def close(self):
        self.stop.set(); self.thread.join(10)
        if self.thread.is_alive(): self.result['error'] = '相机读取尚未结束'


class JointMotionDiagnostic:
    fields = ('Present_Position', 'Goal_Position', 'Present_Velocity', 'Present_Load', 'Present_Current', 'Present_Voltage', 'Status')
    parameters = ('P_Coefficient', 'I_Coefficient', 'D_Coefficient', 'Minimum_Startup_Force', 'CW_Dead_Zone', 'CCW_Dead_Zone', 'Operating_Mode')

    def __init__(self, args):
        self.args = args; self.arm = None; self.phase = {'mode': 'preparing', 'stage': -1}
        self.directory = CORE / 'data/motion_diagnostics' / datetime.now().strftime('%Y%m%d-%H%M%S')
        self.directory.mkdir(parents=True)
        self.report = {'port': args.port, 'joint': args.joint, 'degrees': args.degrees, 'cycles': args.cycles, 'physical': True, 'trials': [], 'timestamp_basis': 'host_receive_time', 'register_units': 'raw SDK decoded; load is PWM proxy, not measured torque'}
        self.parameter_backup = None
        self.p_value = None

    @staticmethod
    def write_p(bus, values):
        if any(bus.sync_read('Torque_Enable', normalize=False).values()):
            raise RuntimeError('内部参数只能在失能时调整')
        for joint, value in values.items():
            lock = bus.read('Lock', joint, normalize=False)
            try:
                bus.write('Lock', joint, 0, normalize=False)
                bus.write('P_Coefficient', joint, value, normalize=False)
                if bus.read('P_Coefficient', joint, normalize=False) != value:
                    raise RuntimeError('内部 P 读回不一致')
            finally:
                bus.write('Lock', joint, lock, normalize=False)

    def save(self):
        (self.directory / 'report.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf8')

    def disconnect(self):
        if self.arm:
            arm = self.arm; self.arm = None
            arm.disconnect()
            if self.parameter_backup is not None:
                arm.connect()
                try:
                    self.write_p(arm._connected(), self.parameter_backup)
                    self.parameter_backup = None
                finally:
                    arm._connected().disconnect(disable_torque=False)
                    arm._bus = None
            return arm.release_result

    def trial(self, enabled, origin):
        mode = 'outer_on' if enabled else 'outer_off'
        if self.p_value is not None: mode += f'_p{self.p_value}'
        self.phase.update(mode=mode, stage=-1)
        self.arm = HardwareWorkflow(CORE / 'configs' / self.args.profile).arm('follower')
        if self.arm.port != self.args.port: raise ValueError('配置串口不匹配')
        self.arm.software_pid_enabled = enabled
        self.arm.max_velocity = min(self.arm.max_velocity, .08)
        self.arm.connect(); bus = self.arm._connected()
        if self.p_value is not None:
            self.parameter_backup = {n: bus.read('P_Coefficient', n, normalize=False) for n in ('elbow_flex', 'wrist_flex')}
            self.report.setdefault('original_p', self.parameter_backup.copy())
            self.save()
            self.write_p(bus, {n: self.p_value for n in self.parameter_backup})
        before = {field: bus.sync_read(field, normalize=False) for field in self.parameters}
        start = dict(self.arm.read_observation().joint_positions)
        if origin is None: origin = dict(start)
        target = dict(origin); limit = self.arm.limits.joints[self.args.joint]
        direction = 1 if (limit.lower + limit.upper) / 2 > origin[self.args.joint] else -1
        target[self.args.joint] += direction * math.radians(self.args.degrees)
        self.arm.limits.validate(origin); self.arm.limits.validate(target)
        trial = {'mode': mode, 'origin': origin, 'enable_pose': start, 'target': target, 'parameters': before, 'samples': []}
        self.report['trials'].append(trial)
        time.sleep(3)
        print(json.dumps({'mode': mode, 'message': '开始固定往返'}, ensure_ascii=False), flush=True)
        self.arm.arm(); trial['motion_registers'] = {field: bus.sync_read(field, normalize=False) for field in ('Phase','Goal_Velocity','Acceleration')}; began = time.monotonic(); next_tick = began
        with (self.directory / (mode + '-feedback.jsonl')).open('w', encoding='utf8') as out:
            while time.monotonic() - began < self.args.cycles * 2 * self.args.hold:
                t = time.monotonic() - began; stage = int(t / self.args.hold)
                self.phase['stage'] = stage
                requested = target if stage % 2 == 0 else origin
                self.arm.send_action(Action(requested))
                sample = {'t': t, 'at_ns': time.time_ns(), 'stage': stage, 'requested_rad': requested, 'commanded_rad': self.arm.applied_action.joint_positions}
                for field in self.fields: sample[field] = bus.sync_read(field, normalize=False)
                if len(trial['samples']) % 10 == 0: sample['Present_Temperature'] = bus.sync_read('Present_Temperature', normalize=False)
                sample['read_finished_ns'] = time.time_ns()
                sample['actual_rad'] = self.arm.calibration.angles(sample['Present_Position'])
                trial['samples'].append(sample); out.write(json.dumps(sample, ensure_ascii=False) + '\n')
                if any(sample['Status'].values()): raise RuntimeError('舵机状态非零，停止当前对照')
                next_tick += 1 / 30
                time.sleep(max(0, next_tick - time.monotonic()))
                if time.monotonic() - next_tick > .1: next_tick = time.monotonic()
        trial['parameters_after'] = {field: bus.sync_read(field, normalize=False) for field in self.parameters}
        trial['parameters_unchanged'] = before == trial['parameters_after']
        trial['diagnostics'] = self.arm.control_diagnostics
        trial['release'] = self.disconnect()
        trial['stages'] = []
        for stage in range(self.args.cycles * 2):
            rows = [s for s in trial['samples'] if s['stage'] == stage]
            tail = [s for s in rows if s['t'] >= rows[-1]['t'] - 1]
            joint = self.args.joint
            trial['stages'].append({'stage': stage, 'mean_error_deg': math.degrees(sum(s['requested_rad'][joint] - s['actual_rad'][joint] for s in tail) / len(tail)), 'tail_peak_to_peak_ticks': max(s['Present_Position'][joint] for s in tail) - min(s['Present_Position'][joint] for s in tail), 'max_encoder_step_ticks': max(abs(b['Present_Position'][joint] - a['Present_Position'][joint]) for a,b in zip(rows, rows[1:])), 'max_goal_step_ticks': max(abs(b['Goal_Position'][joint] - a['Goal_Position'][joint]) for a,b in zip(rows, rows[1:])), 'tail_goal_changes': sum(a['Goal_Position'][joint] != b['Goal_Position'][joint] for a,b in zip(tail,tail[1:]))})
        self.save()
        print(json.dumps({'mode': mode, 'stages': trial['stages'], 'release': trial['release']}, ensure_ascii=False), flush=True)
        if not trial['release'].get('torque_disabled') or not trial['release'].get('start_reached'): raise RuntimeError('未确认回位失能，不继续下轮')
        return origin

    def run(self):
        recorder = None; paused = False
        try:
            if any(s['port'] == self.args.port and s['status'] in ('connecting','ready','moving','returning_zero') for s in BlockWorkflow.http('hardware/arms')['sessions']): raise RuntimeError('请先停止已有真机控制')
            devices = [c for c in BlockWorkflow.http('cameras')['cameras'] if c.get('physical')]
            selected = next((c for c in devices if c['id'] == self.args.camera), None) if self.args.camera != 'auto' else next((c for c in devices if 'icspring' in c['name'].lower()), None)
            if selected:
                recorder = CameraRecorder(self.directory, selected['id'], self.phase); recorder.start(); self.report['camera'] = {'name': selected['name'], **recorder.result}
            else: self.report['camera'] = {'error': '未找到指定真实相机'}
            BlockWorkflow.http(f'hardware/arms/{self.args.port}/observe-stop', {}); paused = True
            origin = None
            if self.args.compare_p:
                origin = self.trial(False, origin)
                for self.p_value in self.args.p_values: origin = self.trial(False, origin)
            else:
                for enabled in ([False, True] if self.args.mode == 'compare' else [self.args.mode == 'on']): origin = self.trial(enabled, origin)
        except KeyboardInterrupt: self.report['cancelled'] = True
        except Exception as error: self.report['error'] = str(error)
        finally:
            self.phase.update(mode='release')
            try:
                release = self.disconnect()
                if release: self.report['cleanup_release'] = release
            except Exception as error: self.report['release_error'] = str(error)
            if paused:
                try: BlockWorkflow.http(f'hardware/arms/{self.args.port}/observe-resume', {}); self.report['observer_resumed'] = True
                except Exception as error: self.report['resume_error'] = str(error)
            if recorder: recorder.close(); self.report['camera'] = {'name': selected['name'], **recorder.result}
            self.save(); print(json.dumps({'report': str(self.directory / 'report.json'), 'error': self.report.get('error'), 'release_error': self.report.get('release_error'), 'camera': self.report.get('camera')}, ensure_ascii=False), flush=True)
        return 1 if self.report.get('error') or self.report.get('release_error') else 130 if self.report.get('cancelled') else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM17'); parser.add_argument('--profile', default='so100.local.yaml')
    parser.add_argument('--joint', default='wrist_flex', choices=('shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll','gripper'))
    parser.add_argument('--degrees', type=float, default=4); parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--hold', type=float, default=4); parser.add_argument('--mode', choices=('off','on','compare'), default='off'); parser.add_argument('--camera', default='auto')
    parser.add_argument('--compare-p', action='store_true', help='对比原始参数与 M3/M4 P=16、8；每轮结束恢复原参数')
    parser.add_argument('--p-values', type=int, nargs='+', default=[16, 8])
    args = parser.parse_args()
    if any(value < 1 or value > 254 for value in args.p_values): parser.error('P 必须在 1–254 之间')
    if not math.isfinite(args.degrees) or args.degrees <= 0 or not math.isfinite(args.hold) or args.hold < 1 or args.cycles < 1: parser.error('角度、循环次数及停留时长无效')
    EnvironmentSettings.load(); return JointMotionDiagnostic(args).run()

if __name__ == '__main__': raise SystemExit(main())

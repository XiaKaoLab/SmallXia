"""功能：ACT 策略读取真机反馈与真实画面，闭环下发模型坐标动作。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from time import monotonic, sleep, time_ns

from ..contracts import Observation
from ..communication.control_heartbeat import ControlHeartbeat
from ..communication.motion_progress import MotionProgress
from .policy_images import PolicyImages


class HardwarePolicyRollout:
    def __init__(self, worker):
        self.worker = worker
        self.request = worker.request
        self.port = self.request['target'].removeprefix('serial:')
        self.endpoint = f'/api/v1/hardware/arms/{self.port}'

    def state(self):
        state = self.worker.http(self.endpoint)
        if state['status'] not in ('ready', 'moving'):
            raise RuntimeError(state.get('error') or '请先使能机械臂')
        if state.get('feedback_age_ms') is None or state['feedback_age_ms'] > 500:
            raise RuntimeError('未收到当前真机反馈')
        return state

    def run(self, policy, execute):
        period = 1 / self.request['fps']
        camera = PolicyImages(policy.metadata, self.request.get('camera_sources', {}))
        heartbeat = None
        completed = 0
        last_dispatch = monotonic()
        try:
            self.state()
            heartbeat = ControlHeartbeat(self.port).start()
            for step in range(self.request['steps']):
                started = monotonic()
                images, image_timing = camera.read()
                state = self.state()
                observed = state['render_joint_positions']
                observation = Observation(state.get('observed_at_ns', time_ns()), observed, {})
                infer_started = monotonic()
                action = policy.predict(observation, images=images)
                infer_finished = monotonic()
                if not execute:
                    return {'joint_positions': action.joint_positions, 'frame': 'so100_mid_calib',
                            'unit': 'rad', 'physical': True, 'executed': False, 'target': self.request['target']}
                # 模型限速后，由已有控制器逆转换到编码器坐标并执行平滑轨迹。
                latest = self.state()
                dispatch_at = monotonic()
                interval = max(period, dispatch_at - last_dispatch)
                safe = policy.limits.constrain(action, latest['render_joint_positions'], interval, .15)
                receipt = self.worker.http(self.endpoint + '/motions', {
                    'joint_positions': safe.joint_positions, 'unit': 'rad', 'frame': 'so100_mid_calib',
                    'max_velocity': .15})
                last_dispatch = dispatch_at
                completed += 1
                self.worker.progress(step=completed, total_steps=self.request['steps'],
                                     physical=True, target=self.request['target'], last_receipt=receipt,
                                     observation_at_ns=observation.timestamp_ns,
                                     execution_feedback_at_ns=latest.get('observed_at_ns'),
                                     observation_age_ms=round((time_ns()-observation.timestamp_ns)/1e6, 2),
                                     inference_ms=round((infer_finished-infer_started)*1000, 2),
                                     capture_ms=round((infer_started-started)*1000, 2),
                                     cycle_ms=round((monotonic()-started)*1000, 2),
                                     effective_fps=round(1/interval, 2), **image_timing)
                sleep(max(0, period - (monotonic() - started)))
            # 最后一帧也必须有实际到位反馈，不能用接收成功冒充完成。
            state = self.state()
            expected = receipt['motion_id']
            progress = MotionProgress()
            while True:
                if state['motion_id'] != expected:
                    raise RuntimeError('策略目标已被其他动作替换')
                if state['status'] == 'ready' and state['reached_motion_id'] == expected:
                    break
                progress.update(state['joint_positions'], state['target'])
                sleep(.05)
                state = self.state()
            return {'steps': completed, 'executed': True, 'physical': True,
                    'target': self.request['target'], 'task_success_validated': False,
                    'last_receipt': state}
        except Exception:
            if execute:
                try: self.worker.http(self.endpoint + '/disable', {})
                except Exception: pass  # 保留原始错误；控制失联由已有会话释放。
            raise
        finally:
            if heartbeat: heartbeat.close()

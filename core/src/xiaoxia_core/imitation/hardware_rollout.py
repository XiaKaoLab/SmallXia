"""功能：ACT 策略读取真机反馈与真实画面，闭环下发模型坐标动作。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
import base64
from time import monotonic, sleep, time_ns

from ..contracts import Observation
from ..collection.frame_client import CameraFrameClient
from ..communication.control_heartbeat import ControlHeartbeat


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
        from PIL import Image
        period = 1 / self.request['fps']
        camera = CameraFrameClient()
        heartbeat = None
        completed = 0
        try:
            self.state()
            heartbeat = ControlHeartbeat(self.port).start()
            for step in range(self.request['steps']):
                started = monotonic()
                images = {}
                for key, shape in policy.metadata['images'].items():
                    source = self.request.get('camera_sources', {}).get(key, key)
                    if source != 'real' and not source.startswith('opencv_'):
                        raise ValueError('真机策略需要为模型图像选择真实摄像头')
                    frame = camera.read(source)
                    path = self.worker.directory / f'hardware-image-{len(images)}.jpg'
                    path.write_bytes(base64.b64decode(frame['image_base64']))
                    resized = None
                    with Image.open(path) as image:
                        if image.size != (shape[1], shape[0]):
                            resized = image.convert('RGB').resize((shape[1], shape[0]))
                    if resized is not None:
                        resized.save(path)
                    images[key] = str(path)
                state = self.state()
                observed = state['render_joint_positions']
                observation = Observation(state.get('observed_at_ns', time_ns()), observed, images)
                action = policy.predict(observation)
                if not execute:
                    return {'joint_positions': action.joint_positions, 'frame': 'so100_mid_calib',
                            'physical': True, 'executed': False, 'target': self.request['target']}
                # 模型限速后，由已有控制器逆转换到编码器坐标并执行平滑轨迹。
                self.state()
                safe = policy.limits.constrain(action, observed, period, .15)
                receipt = self.worker.http(self.endpoint + '/motions', {
                    'joint_positions': safe.joint_positions, 'unit': 'rad', 'frame': 'so100_mid_calib'})
                completed += 1
                self.worker.progress(step=completed, total_steps=self.request['steps'],
                                     physical=True, target=self.request['target'], last_receipt=receipt)
                sleep(max(0, period - (monotonic() - started)))
            # 最后一帧也必须有实际到位反馈，不能用接收成功冒充完成。
            state = self.state()
            while state['status'] == 'moving':
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

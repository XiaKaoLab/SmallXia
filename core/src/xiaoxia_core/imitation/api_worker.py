"""隔离执行 LeRobot 导出、ACT 训练及仅面向 table 的策略推理和回放。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import base64
import json
import os
import sys
from pathlib import Path
from threading import Thread
from time import monotonic, sleep, time, time_ns
from urllib.request import Request, urlopen
from uuid import uuid4

from .api_jobs import atomic_json


class ImitationWorker:
    def __init__(self, directory):
        self.directory = directory
        self.request = json.loads((directory / 'request.json').read_text(encoding='utf-8'))
        self.state = json.loads((directory / 'status.json').read_text(encoding='utf-8'))

    def progress(self, **values):
        self.state.update(values)
        atomic_json(self.directory / 'status.json', self.state)

    def export(self):
        from ..contracts import Action, Observation
        from ..safety import JointLimits
        from .dataset import DemonstrationWriter
        source = Path(self.request['dataset_directory'])
        manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
        urdf = Path(__file__).resolve().parents[4] / 'table/public/robots/so101/so101_new_calib.urdf'
        limits = JointLimits.from_urdf(urdf)
        writer = None
        written = 0
        try:
            for episode in range(manifest['episodes']):
                rows = 0
                with (source / f'episode-{episode:05d}.jsonl').open(encoding='utf-8') as stream:
                    for line in stream:
                        row = json.loads(line)
                        observation = Observation(row['timestamp_ns'], row['observation'],
                                                  {name: str(source / path) for name, path in row['images'].items()})
                        if writer is None:
                            writer = DemonstrationWriter(self.directory / 'dataset', f"local/{manifest['id']}",
                                manifest['fps'], limits, observation, simulated=True, robot_type='so101_table_model')
                            writer.metadata.update(state_source=manifest['state_source'],
                                camera_sources=manifest['cameras'], camera_joint_synchronized=False,
                                action_semantics='explicit_demonstrator_target_not_dispatched_by_record_api')
                            atomic_json(self.directory / 'dataset/imitation.json', writer.metadata)
                        writer.append(observation, Action(row['action']), manifest['task'])
                        written += 1
                        rows += 1
                        self.progress(frames=written, total_frames=manifest['total_frames'])
                if rows < 2:
                    raise ValueError('episode 帧数不足')
                writer.save_episode()
            if written != manifest['total_frames']:
                raise ValueError('记录帧数与 manifest 不一致，数据集不能作为完成状态使用')
        finally:
            if writer:
                writer.close()
        return {'dataset_id': manifest['id'], 'frames': written, 'episodes': manifest['episodes'],
                'dataset': str(self.directory / 'dataset'), 'format': 'LeRobotDataset', 'physical': False}

    def train(self):
        from .act import ACTTrainer, ACTTrainingConfig
        configuration = ACTTrainingConfig(dataset=Path(self.request['dataset']), output=self.directory / 'checkpoint',
            **{key: self.request[key] for key in ('steps', 'batch_size', 'chunk_size', 'device')})
        return ACTTrainer().train(configuration, progress=lambda step, loss: self.progress(step=step, loss=loss, total_steps=configuration.steps))

    @staticmethod
    def http(path, body=None):
        request = Request('http://127.0.0.1:8766' + path,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    def predict(self, rollout=False):
        from ..collection.frame_client import CameraFrameClient
        from ..contracts import Observation
        from .act import ACTJointPolicy
        policy = ACTJointPolicy(self.request['device'])
        policy.load(Path(self.request['checkpoint']))
        client = CameraFrameClient()
        period = 1 / self.request['fps']
        receipts = []
        for step in range(self.request['steps']):
            started = monotonic()
            state = self.http('/api/v1/robots/table/state')
            images = {}
            for source in policy.metadata['images']:
                if source not in ('virtual', 'real'):
                    raise ValueError('检查点相机名称不属于统一画面 API')
                frame = client.read(source)
                path = self.directory / f'{source}.jpg'
                path.write_bytes(base64.b64decode(frame['image_base64']))
                images[source] = str(path)
            observation = Observation(time_ns(), state['joint_positions'], images)
            action = policy.predict(observation)
            if not rollout:
                return {'joint_positions': action.joint_positions, 'unit': 'rad', 'executed': False, 'physical': False}
            # 模型动作走既有运动 API：速度约束后继续由模型碰撞边界裁剪。
            limits = policy.limits
            safe = limits.constrain(action, state['joint_positions'], period, 0.25)
            receipt = self.http('/api/v1/robots/table/motions', {'request_id': str(uuid4()),
                'expires_at_ms': int(time() * 1000) + 900, 'unit': 'rad', 'joint_positions': safe.joint_positions})
            receipts.append(receipt)
            self.progress(step=step + 1, total_steps=self.request['steps'], last_receipt=receipt)
            sleep(max(0, period - (monotonic() - started)))
        return {'steps': len(receipts), 'executed': True, 'target': 'table', 'physical': False,
                'task_success_validated': False, 'last_receipt': receipts[-1]}

    def watch_parent(self):
        # 服务进程异常退出时也终止任务，避免重启后留下孤立训练/回放。
        parent_pid = self.request['parent_pid']
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x00100000, False, parent_pid)
            if handle:
                kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
                kernel.CloseHandle(handle)
            os._exit(2)
        while os.getppid() == parent_pid:
            sleep(1)
        os._exit(2)

    def run(self):
        Thread(target=self.watch_parent, daemon=True).start()
        self.progress(status='running', started_at_ns=time_ns())
        try:
            kind = self.request['kind']
            if kind == 'export':
                result = self.export()
            elif kind == 'train':
                result = self.train()
            elif kind in ('predict', 'rollout'):
                result = self.predict(rollout=kind == 'rollout')
            else:
                raise ValueError('未知任务')
            self.progress(status='succeeded', result=result, finished_at_ns=time_ns())
        except Exception as error:
            self.progress(status='failed', error=f'{type(error).__name__}: {error}', finished_at_ns=time_ns())
            raise


if __name__ == '__main__':
    ImitationWorker(Path(sys.argv[1])).run()

"""简化示教、导出、训练及仿真推理，自动解析最近的数据和模型并等待实际完成。
Created on 2026-11-02; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
import json
import os
from pathlib import Path
from time import monotonic, sleep
from urllib.request import Request, urlopen

from ..imitation.api_client import ImitationClient
from ..imitation.api_jobs import atomic_json


class BlockWorkflow:
    root = Path(__file__).resolve().parents[3] / 'data/block_workflow'

    def __init__(self):
        self.client = ImitationClient()
        self.root.mkdir(parents=True, exist_ok=True)

    def state(self):
        path = self.root / 'current.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

    def remember(self, **values):
        atomic_json(self.root / 'current.json', {**self.state(), **values})

    @staticmethod
    def emit(stage, **values):
        print(json.dumps({'workflow': {'stage': stage, **values}}, ensure_ascii=False), flush=True)

    @staticmethod
    def track(endpoint):
        directory = os.environ.get('XIAOXIA_PROGRAM_DIR')
        if directory:
            path = Path(directory) / 'children.json'
            children = json.loads(path.read_text()) if path.exists() else []
            if endpoint not in children:
                atomic_json(path, [*children, endpoint])

    @classmethod
    def track_created(cls, namespace, endpoint, body, result):
        if body is None or not isinstance(result, dict) or endpoint.endswith('/stop'):
            return
        if namespace in ('imitation', 'reinforcement') and result.get('kind') and result.get('id'):
            cls.track(f'{namespace}/jobs/{result["id"]}/stop')
        if namespace == 'collection':
            identity = result.get('session_id') or (result.get('id') if '/sessions' in endpoint or endpoint.startswith('sessions/') else None)
            if identity:
                cls.track(f'collection/sessions/{identity}/stop')
        if namespace == 'hardware' and endpoint.rsplit('/',1)[-1] in ('connect','enable'):
            cls.track('hardware/' + endpoint.rsplit('/',1)[0] + '/stop')

    def cleanup(self, directory, hardware_only=False):
        path = directory / 'children.json'
        for endpoint in json.loads(path.read_text()) if path.exists() else []:
            if hardware_only and not endpoint.startswith('hardware/'):
                continue
            try:
                self.http(endpoint, {})
            except Exception:
                pass

    @staticmethod
    def http(endpoint, body=None):
        from urllib.error import HTTPError
        request = Request('http://127.0.0.1:8766/api/v1/' + endpoint,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        try:
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
                namespace, _, path = endpoint.partition('/')
                BlockWorkflow.track_created(namespace, path, body, result)
                return result
        except HTTPError as error:
            raise RuntimeError(json.loads(error.read()).get('error', str(error))) from None

    def wait_job(self, job, namespace='imitation', timeout=86400):
        self.track(f'{namespace}/jobs/{job["id"]}/stop')
        deadline = monotonic() + timeout
        previous = None
        while True:
            state = self.http(f'{namespace}/jobs/{job["id"]}')
            progress = (state['status'], state.get('step'), state.get('frames'))
            if progress != previous:
                self.emit(state['kind'], status=state['status'], step=state.get('step'),
                          total=state.get('total_steps'), frames=state.get('frames'))
                previous = progress
            if state['status'] == 'succeeded' and state.get('process_exited', True):
                return state
            if state['status'] not in ('queued', 'running', 'succeeded'):
                raise RuntimeError(state.get('error', '任务未完成'))
            if monotonic() > deadline:
                self.http(f'{namespace}/jobs/{job["id"]}/stop', {})
                raise TimeoutError('等待任务超时')
            sleep(.2)

    def wait_result(self, receipt):
        if not isinstance(receipt, dict):
            raise ValueError('请接入任务回执')
        if receipt.get('kind') in ('ball_pickup', 'ball_onnx_rollout', 'ball_onnx_export'):
            return self.wait_job(receipt, 'reinforcement')
        if 'command_id' in receipt:
            identity = receipt['session_id']
            self.track(f'collection/sessions/{identity}/stop')
            deadline = monotonic() + 86400
            while monotonic() < deadline:
                result = self.http(f'collection/sessions/{identity}/commands/{receipt["command_id"]}')
                if result['status'] == 'succeeded':
                    return result
                if result['status'] == 'failed':
                    raise RuntimeError(str(result.get('result', '采集失败')))
                sleep(.2)
            raise TimeoutError('等待采集超时')
        return self.wait_job(receipt)

    def begin(self, task='机械臂示教', camera='none'):
        dataset = self.client.create_dataset(task, fps=2, cameras=[] if camera == 'none' else [camera], action_semantics='waypoint_next_target')
        self.remember(dataset_id=dataset['id'])
        self.emit('示教已开始')
        return dataset

    def record_pose(self):
        identity = self.state().get('dataset_id')
        if not identity:
            raise ValueError('请先开始示教')
        # 此积木显式指定当前仿真目标作为示教动作标签；不是实机反馈动作。
        target = self.http('robots/table/state')['joint_positions']
        state = self.client.dataset(identity)
        remaining = 1 / state['fps'] - (__import__('time').time_ns() - state.get('last_sample_ns', 0)) / 1e9
        if remaining > 0:
            sleep(remaining)
        result = self.client.record_frame(identity, target)
        self.emit('记录姿态', frames=result['total_frames'])
        return result

    def finish(self):
        identity = self.state().get('dataset_id')
        if not identity:
            raise ValueError('没有正在记录的示教')
        result = self.client.finalize(identity)
        if result.get('kind') == 'export':
            self.wait_job(result)
        self.emit('示教已保存')
        return self.client.dataset(identity)

    def catalog(self):
        datasets = self.client.request('datasets')['datasets']
        sessions = self.http('collection/sessions')['sessions']
        ready = [dict(row, label=f"{row['task']} · {row['total_frames']} 帧") for row in datasets if row.get('export_status') == 'succeeded' and row.get('model_frame') == 'so100_mid_calib']
        def compatible(path):
            try:
                return json.loads((Path(path) / 'imitation.json').read_text(encoding='utf-8')).get('model_frame') == 'so100_mid_calib'
            except (OSError, ValueError):
                return False
        ready += [dict(row, total_frames=row.get('frames', 0), label=f"{row['task']} · {row.get('frames', 0)} 帧")
                  for row in sessions if row.get('phase') == 'completed' and row.get('record_actions') and row.get('job', {}).get('status') == 'succeeded'
                  and compatible(row['job']['result']['dataset'])]
        jobs = self.client.request('jobs')['jobs']
        models = [dict(row, label=f"示教模型 · {row['result']['steps']} 步 · {row['id'][:8]}") for row in jobs if row['kind'] == 'train' and row['status'] == 'succeeded'
                  and compatible(row['result']['checkpoint'])]
        return {'datasets': sorted(ready, key=lambda row: row.get('created_at_ns', 0), reverse=True),
                'models': sorted(models, key=lambda row: row.get('created_at_ns', 0), reverse=True)}

    def train(self, dataset_id='latest', steps=1000, device='cpu'):
        datasets = self.catalog()['datasets']
        dataset = next((row for row in datasets if dataset_id == 'latest' or row['id'] == dataset_id), None)
        if not dataset:
            raise ValueError('请先保存至少两帧带动作标签的示教')
        frames = dataset['total_frames']
        if frames < 2:
            raise ValueError('示教至少需要两帧')
        job = self.client.train(dataset['id'], steps=steps, device=device,
                                chunk_size=min(16, frames), batch_size=min(4, frames))
        self.wait_job(job)
        self.remember(training_id=job['id'])
        self.emit('训练完成')
        return job

    def play(self, dataset_id='latest'):
        from time import time
        from uuid import uuid4
        datasets = self.catalog()['datasets']
        selected = next((row for row in datasets if dataset_id == 'latest' or row['id'] == dataset_id), None)
        if not selected:
            raise ValueError('请先保存示教')
        directory = self.root.parent / 'imitation_api/datasets' / selected['id']
        if directory.is_dir():
            poses = [json.loads(line)['observation'] for path in sorted(directory.glob('episode-*.jsonl'))
                     for line in path.read_text(encoding='utf-8').splitlines()]
        else:
            from lerobot.datasets.lerobot_dataset import LeRobotDataset
            from ..safety import JOINTS
            directory = Path(selected['job']['result']['dataset'])
            metadata = json.loads((directory / 'imitation.json').read_text(encoding='utf-8'))
            dataset = LeRobotDataset(metadata['repo_id'], root=directory, download_videos=False)
            poses = [dict(zip(JOINTS, row['observation.state'].tolist(), strict=True)) for row in dataset]
        for index, pose in enumerate(poses):
            started = monotonic()
            self.http('robots/table/motions', {'request_id': str(uuid4()), 'expires_at_ms': int(time() * 1000) + 900,
                'unit': 'rad', 'joint_positions': pose})
            self.emit('回放示教', step=index + 1, total=len(poses))
            while monotonic() - started < 1 / selected['fps']:
                sleep(.02)
        return {'frames': len(poses), 'physical': False}

    def run(self, model_id='latest', steps=20, device='cpu', target='simulation', camera_source=None):
        models = self.catalog()['models']
        model = next((row for row in models if model_id == 'latest' or row['id'] == model_id), None)
        if not model:
            raise ValueError('请先训练示教模型')
        job = self.client.rollout(model['id'], steps=steps, device=device, target=target, camera_source=camera_source)
        result = self.wait_job(job)
        self.emit('推理完成')
        return result

"""持久化模仿学习子进程任务，提供状态、日志、停止和重启恢复。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from threading import RLock
from time import time_ns
from uuid import uuid4


def atomic_json(path: Path, value: dict):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{32}', value):
        raise ValueError('ID 必须是服务生成的 32 位标识')
    return value


class ImitationJobs:
    def __init__(self, root: Path, *, worker_module="xiaoxia_core.imitation.api_worker", max_running=1):
        self.root = root
        self.worker_module, self.max_running = worker_module, max_running
        root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._processes = {}
        for path in root.glob('*/status.json'):
            state = json.loads(path.read_text(encoding='utf-8'))
            if state['status'] in ('queued', 'running'):
                atomic_json(path, {**state, 'status': 'interrupted', 'error': '服务已重启，未自动恢复任务'})

    def start(self, kind: str, payload: dict, *, initial_state=None):
        with self._lock:
            if sum(process.poll() is None for process in self._processes.values()) >= self.max_running:
                raise ValueError('后台任务数量已达上限，请等待或停止已有任务')
            job_id = uuid4().hex
            directory = self.root / job_id
            directory.mkdir()
            atomic_json(directory / 'request.json', {'kind': kind, **payload, 'parent_pid': os.getpid()})
            atomic_json(directory / 'status.json', {**(initial_state or {}), 'id': job_id, 'kind': kind, 'status': 'queued', 'created_at_ns': time_ns()})
            options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
            source = Path(__file__).resolve().parents[2]
            environment = {**os.environ, 'PYTHONPATH': str(source) + os.pathsep + os.environ.get('PYTHONPATH', ''),
                           'PYTHONIOENCODING': 'utf-8', 'USE_TF': '0'}
            try:
                with (directory / 'worker.log').open('wb') as log:
                    self._processes[job_id] = subprocess.Popen(
                        [sys.executable, '-u', '-m', self.worker_module, str(directory)],
                        stdout=log, stderr=log, env=environment, **options)
            except Exception as error:
                atomic_json(directory / 'status.json', {'id': job_id, 'kind': kind, 'status': 'failed', 'error': str(error)})
                raise
            return self.get(job_id)

    def get(self, job_id: str):
        with self._lock:
            directory = self.root / identifier(job_id)
            path = directory / 'status.json'
            state = json.loads(path.read_text(encoding='utf-8'))
            process = self._processes.get(job_id)
            if process is not None and process.poll() is not None and state['status'] in ('queued', 'running'):
                state.update(status='failed', error=f'任务进程异常退出：{process.returncode}')
                atomic_json(path, state)
            log = directory / 'worker.log'
            if log.exists():
                with log.open('rb') as stream:
                    stream.seek(max(0, log.stat().st_size - 8000))
                    state['log_tail'] = stream.read().decode('utf-8', errors='replace')
            return state

    def list(self):
        return [self.get(path.parent.name) for path in self.root.glob('*/status.json')]

    def stop(self, job_id: str):
        with self._lock:
            state = self.get(job_id)
            process = self._processes.get(job_id)
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                state = self.get(job_id)
                if state['status'] != 'succeeded':
                    state.update(status='cancelled', finished_at_ns=time_ns())
                    state.pop('log_tail', None)
                    state.pop('error', None)
                    atomic_json(self.root / job_id / 'status.json', state)
            return self.get(job_id)

    def close(self):
        for job_id in list(self._processes):
            self.stop(job_id)

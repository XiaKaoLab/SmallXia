"""持久化积木程序任务，支持长流程、增量输出与停止，并跟踪子任务清理。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from pathlib import Path

from ..imitation.api_jobs import ImitationJobs, identifier


class ProgramJobsAPI:
    prefix = '/api/v1/programs'

    def __init__(self, root: Path):
        self.jobs = ImitationJobs(root, worker_module='xiaoxia_core.communication.program_worker')

    def handle(self, method, path, body=None):
        parts = path.removeprefix(self.prefix).strip('/').split('/')
        try:
            if method == 'POST' and parts == ['jobs']:
                source = (body or {}).get('source')
                if not isinstance(source, str) or not source.strip() or len(source) > 65536:
                    raise ValueError('程序为空或过长')
                compile(source, '<blocks>', 'exec')
                return 202, self.jobs.start('program', {'source': source})
            if method == 'GET' and parts == ['jobs']:
                return 200, {'jobs': self.jobs.list()}
            if len(parts) == 2 and parts[0] == 'jobs' and method == 'GET':
                return 200, self.jobs.get(identifier(parts[1]))
            if len(parts) == 3 and parts[0] == 'jobs' and parts[2] == 'stop' and method == 'POST':
                identity = identifier(parts[1])
                # 由工作进程清理它启动的采集/训练，再退出；不强杀遗留子任务。
                (self.jobs.root / identity / 'stop').touch()
                return 202, self.jobs.get(identity)
            return 404, {'error': 'route_not_found'}
        except FileNotFoundError:
            return 404, {'error': '程序不存在'}
        except (ValueError, SyntaxError, TypeError) as error:
            return 422, {'error': str(error)}

    def close(self):
        self.jobs.close()

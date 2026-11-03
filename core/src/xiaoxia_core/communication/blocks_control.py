"""为 MCP 与当前 WebView 提供一次投递的受限积木命令及真实回执。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from collections import OrderedDict
from copy import deepcopy
from threading import Condition
from time import monotonic, time_ns
from uuid import uuid4

from ..imitation.api_jobs import identifier


class BlocksControlAPI:
    prefix = '/api/v1/blocks'
    operations = {'observe', 'catalog', 'list', 'create', 'set_fields', 'move', 'connect', 'remove', 'clear', 'export', 'import', 'run'}

    def __init__(self):
        self._condition = Condition()
        self._commands = OrderedDict()

    def _expire(self):
        now = time_ns() // 1000000
        for command in self._commands.values():
            if command['expires_at_ms'] < now and command['status'] in ('queued', 'dispatched'):
                command.update(status='expired' if command['status'] == 'queued' else 'unknown',
                    error='WebView 未返回完成回执；如已投递，操作可能已经生效。先读取工作区/任务状态，不要自动重试。')
        while len(self._commands) > 256:
            self._commands.popitem(last=False)

    def handle(self, method, path, body=None):
        body = body or {}
        parts = path.removeprefix(self.prefix).strip('/').split('/')
        try:
            with self._condition:
                self._expire()
                if method == 'GET' and len(parts) == 2 and parts[0] == 'commands':
                    command = deepcopy(self._commands[identifier(parts[1])])
                    command.pop('client_id', None)
                    return 200, command
                if method != 'POST':
                    return 404, {'error': 'route_not_found'}
                if parts == ['commands']:
                    operation = body.get('operation')
                    arguments = body.get('arguments', {})
                    if operation not in self.operations or not isinstance(arguments, dict):
                        raise ValueError('积木操作或参数无效')
                    if sum(item['status'] in ('queued', 'dispatched') for item in self._commands.values()) >= 32:
                        raise ValueError('积木命令队列已满')
                    command = {'id': uuid4().hex, 'operation': operation, 'arguments': arguments,
                               'status': 'queued', 'expires_at_ms': time_ns() // 1000000 + 15000}
                    self._commands[command['id']] = command
                    self._condition.notify_all()
                    return 202, deepcopy(command)
                if parts == ['poll']:
                    client_id = identifier(body.get('client_id'))
                    deadline = monotonic() + 3
                    while True:
                        self._expire()
                        command = next((item for item in self._commands.values() if item['status'] == 'queued'), None)
                        if command:
                            command.update(status='dispatched', client_id=client_id)
                            return 200, {'command': deepcopy(command)}
                        remaining = deadline - monotonic()
                        if remaining <= 0:
                            return 200, {'command': None}
                        self._condition.wait(timeout=remaining)
                if parts == ['replies']:
                    command = self._commands[identifier(body.get('command_id'))]
                    if command.get('client_id') != identifier(body.get('client_id')):
                        raise ValueError('回执不属于当前 WebView')
                    if command['status'] not in ('dispatched', 'unknown'):
                        raise ValueError('命令已经完成或未投递，不能重复确认')
                    if type(body.get('ok')) is not bool:
                        raise ValueError('ok 需要布尔值')
                    command.update(status='succeeded' if body['ok'] else 'failed',
                                   result=body.get('result'), error=body.get('error'))
                    return 200, {'id': command['id'], 'status': command['status']}
                return 404, {'error': 'route_not_found'}
        except KeyError:
            return 404, {'error': 'command_not_found'}
        except (ValueError, TypeError) as error:
            return 422, {'error': str(error)}

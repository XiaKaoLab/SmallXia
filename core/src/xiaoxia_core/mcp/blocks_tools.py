"""MCP 积木工具通过受限命令桥操作当前 WebView，不执行任意脚本。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import os
from time import monotonic, sleep
from urllib.request import Request, urlopen
from ..imitation.api_jobs import identifier


class BlocksTools:
    @staticmethod
    def request(endpoint, body=None):
        request = Request('http://127.0.0.1:8766/api/v1/blocks/' + endpoint,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def execute(self, operation, arguments=None):
        command = self.request('commands', {'operation': operation, 'arguments': arguments or {}})
        deadline = monotonic() + 9
        while monotonic() < deadline:
            result = self.request('commands/' + command['id'])
            if result['status'] == 'succeeded':
                return {'command_id': command['id'], 'status': 'succeeded', 'result': result.get('result')}
            if result['status'] in ('failed', 'unknown', 'expired'):
                raise RuntimeError(f"积木命令 {command['id']} {result['status']}: {result.get('error')}")
            sleep(0.1)
        raise TimeoutError(f"积木命令 {command['id']} 未收到回执，操作可能已生效；先查询状态，不自动重试")

    def blocks_catalog(self) -> dict:
        """读取当前 WebView 的积木分类、类型与字段；创建积木前查询。"""
        return self.execute('catalog')

    def blocks_list(self) -> dict:
        """读取当前工作区的积木 ID、类型、字段与坐标，不执行程序。"""
        return self.execute('list')

    def blocks_create(self, block_type: str, fields: dict | None = None, x: float = 16, y: float = 24) -> dict:
        """在当前工作区创建一个目录中的积木；字段和数量受现有校验约束，不运行。"""
        return self.execute('create', {'type': block_type, 'fields': fields or {}, 'x': x, 'y': y})

    def blocks_set_fields(self, block_id: str, fields: dict) -> dict:
        """修改积木字段，角度字段为 rad；不触发滑杆的实时发送，也不运行程序。"""
        return self.execute('set_fields', {'id': block_id, 'fields': fields})

    def blocks_move(self, block_id: str, x: float, y: float) -> dict:
        """移动一个积木的画布坐标，不发送机械臂动作。"""
        return self.execute('move', {'id': block_id, 'x': x, 'y': y})

    def blocks_connect(self, parent_id: str, child_id: str, input_name: str = '') -> dict:
        """连接积木：input_name 指定命名输入；留空连接下一条语句。类型不匹配则报错。"""
        return self.execute('connect', {'parent_id': parent_id, 'child_id': child_id, 'input_name': input_name})

    def blocks_remove(self, block_id: str) -> dict:
        """删除指定积木及其嵌套内容；应先读取工作区确认 ID。"""
        return self.execute('remove', {'id': block_id})

    def blocks_clear(self) -> dict:
        """清空工作区；只在用户明确要求清空时调用，先导出备份。"""
        return self.execute('clear')

    def blocks_export(self) -> dict:
        """导出保留变量、嵌套连接和字段的 version=2 工作区快照。"""
        return self.execute('export')

    def blocks_import(self, snapshot: dict) -> dict:
        """用已校验的快照替换当前工作区；覆盖前先导出。不会自动运行。"""
        return self.execute('import', {'snapshot': snapshot})

    def blocks_run(self) -> dict:
        """运行当前积木程序。可能发送模型动作、启动采集/训练；仅在用户明确要求运行时调用。失败不自动重试。"""
        return self.execute('run')

    def blocks_command_status(self, command_id: str) -> dict:
        """超时后查询已有命令的回执，不重新执行。"""
        return self.request('commands/' + identifier(command_id))

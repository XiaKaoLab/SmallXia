"""MCP 积木工具通过受限命令桥操作当前 WebView，不执行任意脚本。
Created on 2026-11-02; Updated on 2026-11-03
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
        """读取积木类型、字段和 connections 连接口；previous/next 可串接语句，inputs 给出循环体、条件和值的命名接口。创建/拼接前查询。"""
        return self.execute('catalog')

    def blocks_list(self) -> dict:
        """读取当前积木和真实连接图：next_id 是下一句，previous_id 是上一句，parent_id 是父块，inputs 是命名输入口到子块ID的映射。用于确认整段程序已接好；坐标相邻不等于连接。不执行。"""
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
        """拼接程序。input_name 留空把 child 接到 parent 的下一句；指定目录中的命名输入可接循环/条件子语句或数值/变量块。返回真实连接图，应检查 next_id 或 inputs 确认。不执行。"""
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
        """提交当前积木程序，返回 program.id 后用 blocks_program_status 查询实际完成。可能包含真机运动，运行前核对目标与用户意图。"""
        return self.execute('run')

    def blocks_programs(self) -> dict:
        """查询后台积木程序，窗口刷新后仍可查看。"""
        from ..blocks.workflow import BlockWorkflow
        return BlockWorkflow.http('programs/jobs')

    def blocks_program_status(self, program_id: str) -> dict:
        """查询指定程序的真实状态和输出；提交成功不代表程序已完成。"""
        from ..blocks.workflow import BlockWorkflow
        return BlockWorkflow.http('programs/jobs/' + identifier(program_id))

    def blocks_program_stop(self, program_id: str) -> dict:
        """停止指定程序，并清理其启动的采集/训练和真机控制。"""
        from ..blocks.workflow import BlockWorkflow
        return BlockWorkflow.http('programs/jobs/' + identifier(program_id) + '/stop', {})

    def blocks_command_status(self, command_id: str) -> dict:
        """超时后查询已有命令的回执，不重新执行。"""
        return self.request('commands/' + identifier(command_id))

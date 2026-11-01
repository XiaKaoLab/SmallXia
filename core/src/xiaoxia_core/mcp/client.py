"""为同步 Agent 托管标准 MCP stdio 会话，保持异步上下文同任务退出。
Created on 2026-11-01; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""

import os
import sys
from contextlib import ExitStack, asynccontextmanager
from datetime import timedelta

from anyio.from_thread import start_blocking_portal
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TableMCPClient:
    @asynccontextmanager
    async def _session(self):
        params = StdioServerParameters(command=sys.executable,
                                      args=["-m", "xiaoxia_core.mcp.server"], env=dict(os.environ))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=20)) as session:
                await session.initialize()
                yield session

    def __enter__(self):
        self._stack = ExitStack()
        try:
            self.portal = self._stack.enter_context(start_blocking_portal())
            self.session = self._stack.enter_context(self.portal.wrap_async_context_manager(self._session()))
            listed = self.portal.call(self.session.list_tools)
            self.names = {tool.name for tool in listed.tools}
            self.tools = [{"type": "function", "name": tool.name,
                           "description": tool.description or "", "parameters": tool.inputSchema,
                           "strict": False} for tool in listed.tools]
            return self
        except BaseException:
            self._stack.close()
            raise

    def call(self, name: str, arguments: dict) -> dict:
        if name not in self.names:
            raise ValueError("未知 MCP 工具")
        result = self.portal.call(self.session.call_tool, name, arguments)
        return result.model_dump(mode="json", exclude_none=True)

    def __exit__(self, *args):
        return self._stack.__exit__(*args)

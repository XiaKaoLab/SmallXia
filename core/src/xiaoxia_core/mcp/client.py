"""为同步 Agent 托管标准 MCP stdio 会话，保持异步上下文同任务退出。
Created on 2026-11-01; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

import logging
import os
import sys
from contextlib import ExitStack, asynccontextmanager
from datetime import timedelta

from anyio.from_thread import start_blocking_portal
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TableMCPClient:
    def __init__(self, profile='default', context=None):
        if profile not in ('default','qiling'):raise ValueError('未知 MCP 配置')
        self.profile=profile
        self.context=context or {}

    @asynccontextmanager
    async def _session(self):
        params = StdioServerParameters(command=sys.executable,
                                      args=["-m", "xiaoxia_core.mcp.server"], env={**os.environ, "XIAOXIA_MCP_PROFILE": self.profile,
                                          "XIAOXIA_QILING_TARGET":self.context.get('target','simulation'),
                                          "XIAOXIA_QILING_PROFILE":self.context.get('profile','so100.local.yaml'),
                                          "XIAOXIA_QILING_MOTION":'true' if self.context.get('enable_motion') is True else 'false'})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize()
                yield session

    def __enter__(self):
        self._stack = ExitStack()
        try:
            self.portal = self._stack.enter_context(start_blocking_portal())
            self.session = self._stack.enter_context(self.portal.wrap_async_context_manager(self._session()))
            listed = self.portal.call(self.session.list_tools)
            if self.profile == 'qiling':
                from .qiling_profile import QiLingProfile
                listed.tools = [tool for tool in listed.tools if tool.name in QiLingProfile.tools_for(self.context)]
            self.names = {tool.name for tool in listed.tools}
            self.tools = [{"type": "function", "name": tool.name,
                           "description": tool.description or "", "parameters": tool.inputSchema,
                           "strict": False} for tool in listed.tools]
            return self
        except BaseException:
            try:
                self._stack.close()
            except Exception:
                logging.getLogger(__name__).exception("MCP 初始化失败后的清理异常")
            raise

    def call(self, name: str, arguments: dict) -> dict:
        if name not in self.names:
            raise ValueError("未知 MCP 工具")
        result = self.portal.call(self.session.call_tool, name, arguments)
        return result.model_dump(mode="json", exclude_none=True)

    def __exit__(self, *args):
        # 模型异常不属于MCP异步任务，不能将它注入异步上下文包装成ExceptionGroup。
        try:
            self._stack.close()
        except Exception:
            if not args or args[1] is None:
                raise
            logging.getLogger(__name__).exception("MCP 清理失败，保留原始请求异常")
        return False

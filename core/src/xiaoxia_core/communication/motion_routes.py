"""将 core 动作发送到机器人 HTTP 路由；不自动连接、使能或重试运动。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import json
from math import isfinite
from time import monotonic_ns, time
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from ..contracts import Action, Observation
from ..safety import JointLimits
from .transport import RobotTransport


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("运动路由不允许重定向")


class MotionRouteClient(RobotTransport):
    """调用指定 robot_id 的远端控制路由，保持 RobotTransport 接口。"""

    def __init__(self, base_url: str, robot_id: str, limits: JointLimits,
                 *, token: str, timeout: float = 0.2) -> None:
        url = urlsplit(base_url)
        if url.scheme not in ("http", "https") or not url.netloc or url.query or url.fragment or url.username or url.password:
            raise ValueError("需要有效的 HTTP(S) 服务地址，不允许查询串、片段或 URL 凭据")
        if not robot_id or not token or not isfinite(timeout) or not 0 < timeout <= 1:
            raise ValueError("需要 robot_id、访问令牌和 (0, 1] 秒超时")
        self.route = f"{base_url.rstrip('/')}/api/v1/robots/{quote(robot_id, safe='')}"
        self.limits, self.token, self.timeout = limits, token, timeout
        self._connected = False
        self.last_receipt: dict | None = None

    def _request(self, method: str, suffix: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body, allow_nan=False).encode("utf-8")
        request = Request(self.route + suffix, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
        })
        # 无自动重试；超时可能表示远端已执行，调用方必须先查询状态。
        with build_opener(_NoRedirect).open(request, timeout=self.timeout) as response:
            if response.geturl() != request.full_url:
                raise RuntimeError("运动路由不允许重定向")
            payload = response.read(65537)
            if len(payload) > 65536:
                raise ValueError("路由响应超过 64 KiB")
            result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError("路由响应必须为 JSON 对象")
        return result

    def connect(self) -> None:
        self.read_observation()
        self._connected = True

    def disconnect(self) -> None:
        # HTTP 客户端关闭不等于实机停机；接收端负责独立的失联保护。
        self._connected = False

    def read_observation(self) -> Observation:
        result = self._request("GET", "/state")
        if result.get("unit") != "rad":
            raise ValueError("仅支持弧度观测")
        positions = result["joint_positions"]
        self.limits.validate(positions)
        return Observation(monotonic_ns(), positions)

    def send_action(self, action: Action) -> None:
        if not self._connected:
            raise RuntimeError("请先连接运动路由")
        self.limits.validate(action.joint_positions)
        request_id = str(uuid4())
        self.last_receipt = None
        result = self._request("POST", "/motions", {
            "request_id": request_id, "expires_at_ms": int(time() * 1000) + 200,
            "unit": "rad", "joint_positions": action.joint_positions,
        })
        if result.get("request_id") != request_id or result.get("status") != "accepted":
            raise RuntimeError("运动接收确认无效；请读取设备状态后再决定下一步")
        self.last_receipt = result

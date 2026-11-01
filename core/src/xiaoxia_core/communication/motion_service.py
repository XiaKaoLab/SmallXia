"""分发运动 API 到已注册设备；连接与实机使能由宿主显式管理。
Created on 2026-11-01; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""

from collections import OrderedDict
from hmac import compare_digest
from threading import Lock
from time import time
from urllib.parse import unquote
from uuid import UUID

from ..contracts import Action
from ..safety import JointLimits
from .transport import RobotTransport


class MotionRouteService:
    """框架无关路由处理器，返回 (HTTP 状态码, JSON 对象)。"""

    def __init__(self, *, token: str) -> None:
        if not token:
            raise ValueError("运动 API 必须配置访问令牌")
        self._token = token
        self._robots: dict[str, tuple[RobotTransport, JointLimits]] = {}
        self._receipts: OrderedDict[tuple[str, str], tuple[dict, dict]] = OrderedDict()
        self._lock = Lock()

    def register(self, robot_id: str, transport: RobotTransport, limits: JointLimits) -> None:
        with self._lock:
            if not robot_id or robot_id in self._robots:
                raise ValueError("机器人标识为空或重复")
            self._robots[robot_id] = transport, limits

    def handle(self, method: str, path: str, authorization: str,
               body: dict | None = None) -> tuple[int, dict]:
        if not compare_digest(authorization.encode(), f"Bearer {self._token}".encode()):
            return 401, {"error": "unauthorized"}
        parts = path.split("/")
        if len(parts) != 6 or parts[1:4] != ["api", "v1", "robots"]:
            return 404, {"error": "route_not_found"}
        robot_id, endpoint = unquote(parts[4]), parts[5]
        with self._lock:
            if robot_id not in self._robots:
                return 404, {"error": "robot_not_found"}
            transport, limits = self._robots[robot_id]
            try:
                if method == "GET" and endpoint == "state":
                    observation = transport.read_observation()
                    limits.validate(observation.joint_positions)
                    return 200, {"robot_id": robot_id, "unit": "rad",
                                 "joint_positions": observation.joint_positions}
                if method != "POST" or endpoint != "motions":
                    return 405, {"error": "method_or_endpoint_not_allowed"}
                if not isinstance(body, dict) or set(body) != {"request_id", "expires_at_ms", "unit", "joint_positions"}:
                    raise ValueError("请求字段无效")
                request_id = str(UUID(body["request_id"]))
                if request_id != body["request_id"] or body["unit"] != "rad":
                    raise ValueError("需要规范 UUID 和 rad 单位")
                expires = body["expires_at_ms"]
                now = int(time() * 1000)
                if type(expires) is not int or not now < expires <= now + 1000:
                    return 409, {"error": "expired_or_invalid_deadline"}
                # 缓存仅保留有效请求；过期请求即使重复也不能再次执行。
                for key in list(self._receipts):
                    if self._receipts[key][0]["expires_at_ms"] <= now:
                        del self._receipts[key]
                key = robot_id, request_id
                if key in self._receipts:
                    previous, receipt = self._receipts[key]
                    return (200, receipt) if previous == body else (409, {"error": "request_id_conflict"})
                if len(self._receipts) >= 1024:
                    return 429, {"error": "motion_capacity_exceeded"}
                positions = body["joint_positions"]
                if not isinstance(positions, dict) or any(type(value) not in (int, float) for value in positions.values()):
                    raise ValueError("关节位置必须为数值对象")
                limits.validate(positions)
                receipt = {"request_id": request_id, "robot_id": robot_id, "status": "dispatching"}
                # 先占用请求 ID：通信异常也不允许重复发送同一动作。
                self._receipts[key] = ({**body, "joint_positions": dict(positions)}, receipt)
                try:
                    transport.send_action(Action(dict(positions)))
                except Exception:
                    receipt["status"] = "unknown"
                    return 503, {**receipt, "error": "dispatch_failed_read_state_before_retry"}
                receipt.update(getattr(transport, "motion_receipt", {}))
                receipt["status"] = "accepted"
                return 202, dict(receipt)
            except (ValueError, TypeError, KeyError, AttributeError):
                return 422, {"error": "invalid_motion_or_state"}
            except Exception:
                return 503, {"error": "transport_unavailable"}

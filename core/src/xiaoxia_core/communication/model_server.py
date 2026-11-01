"""提供 table 模型专用的本机运动路由；不接触串口或实机。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import json
import os
from hmac import compare_digest
from xml.etree import ElementTree
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic_ns

from ..contracts import Action, Observation
from ..safety import JointLimits
from .motion_service import MotionRouteService
from .transport import RobotTransport
from .virtual_camera import VirtualCameraStore


class ModelTransport(RobotTransport):
    """保存显示目标；state 是模型目标，不是实机反馈或渲染到位回执。"""

    def __init__(self, limits: JointLimits) -> None:
        self.limits = limits
        self.positions = {name: max(limit.lower, min(0.0, limit.upper))
                          for name, limit in limits.joints.items()}

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def read_observation(self) -> Observation:
        return Observation(monotonic_ns(), dict(self.positions))

    def send_action(self, action: Action) -> None:
        self.limits.validate(action.joint_positions)
        self.positions = dict(action.joint_positions)


class ModelHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, token: str, limits: JointLimits) -> None:
        urdf = Path(__file__).resolve().parents[4] / "table/public/robots/so101/so101_new_calib.urdf"
        self.camera = VirtualCameraStore({link.attrib["name"] for link in ElementTree.parse(urdf).getroot().findall("link")})
        self.routes = MotionRouteService(token=token)
        self.routes.register("table", ModelTransport(limits), limits)
        self.read_authorization = f"Bearer {token}"
        super().__init__(("127.0.0.1", 8766), ModelRequestHandler)


class ModelRequestHandler(BaseHTTPRequestHandler):
    allowed_origins = {"http://localhost:1420", "http://127.0.0.1:1420",
                       "http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"}

    def _reply(self, status: int, body: dict) -> None:
        data = json.dumps(body, allow_nan=False).encode("utf-8")
        self.send_response(status)
        origin = self.headers.get("Origin")
        if origin in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        # 仅模型状态允许本机匿名读取；运动写入始终要求令牌。
        if self.path != "/api/v1/robots/table/state":
            self._reply(404, {"error": "route_not_found"})
            return
        status, body = self.server.routes.handle("GET", self.path, self.server.read_authorization)
        self._reply(status, {**body, "source": "display_target", "physical": False, "camera": self.server.camera.snapshot()})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                self._reply(413, {"error": "body_size_invalid"})
                return
            if self.headers.get_content_type() != "application/json":
                self._reply(415, {"error": "json_required"})
                return
            body = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self._reply(400, {"error": "invalid_json"})
            return
        if self.path == "/api/v1/robots/table/camera":
            if not compare_digest(self.headers.get("Authorization", "").encode(), self.server.read_authorization.encode()):
                self._reply(401, {"error": "unauthorized"})
                return
            try:
                configuration = self.server.camera.configure(body)
                self._reply(202, {"status": "accepted", "physical": False, "camera": configuration})
            except ValueError as error:
                self._reply(422, {"error": str(error)})
            return
        status, result = self.server.routes.handle("POST", self.path,
                                                 self.headers.get("Authorization", ""), body)
        self._reply(status, result)

    def log_message(self, format: str, *args) -> None:
        pass

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(2)


def main() -> None:
    token = os.environ.get("XIAOXIA_MOTION_TOKEN", "")
    if not token:
        raise SystemExit("请设置 XIAOXIA_MOTION_TOKEN")
    root = Path(__file__).resolve().parents[4]
    limits = JointLimits.from_urdf(root / "table/public/robots/so101/so101_new_calib.urdf")
    with ModelHTTPServer(token, limits) as server:
        print("table 模型运动 API: http://127.0.0.1:8766；不连接实机", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

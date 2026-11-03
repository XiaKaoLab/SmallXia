"""提供 table 模型专用的本机运动路由；不接触串口或实机。
Created on 2026-11-01; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

import json
import os
from time import time_ns
from uuid import uuid4
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
from .camera_frames import CameraFrames
from .model_pose_guard import ModelPoseGuard
from ..imitation.api_service import ImitationAPI
from ..reinforcement.service import ReinforcementAPI
from ..collection.capture_api import CollectionAPI
from .blocks_control import BlocksControlAPI
from .program_jobs import ProgramJobsAPI
from .hardware_control import HardwareControlAPI


class ModelTransport(RobotTransport):
    """保存显示目标；state 是模型目标，不是实机反馈或渲染到位回执。"""

    def __init__(self, limits: JointLimits, guard: ModelPoseGuard) -> None:
        self.limits = limits
        self.guard = guard
        self.motion_receipt = {}
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
        pose, reason = self.guard.limit_path(self.positions, action.joint_positions)
        self.positions = pose
        self.motion_receipt = {"applied_joint_positions": dict(pose), "limited": bool(reason), "limit_reason": reason}


class ModelHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, token: str, limits: JointLimits) -> None:
        urdf = Path(__file__).resolve().parents[4] / "table/public/robots/so100/so100_mid_calib.urdf"
        self.blocks = BlocksControlAPI()
        self.programs = ProgramJobsAPI(Path(__file__).resolve().parents[3] / 'data/program_jobs')
        self.frames = CameraFrames()
        self.camera = VirtualCameraStore({link.attrib["name"] for link in ElementTree.parse(urdf).getroot().findall("link")})
        self.routes = MotionRouteService(token=token)
        self.routes.register("table", ModelTransport(limits, ModelPoseGuard(urdf)), limits)
        self.read_authorization = f"Bearer {token}"
        self.imitation = ImitationAPI(Path(__file__).resolve().parents[3] / 'data/imitation_api',
            limits, self.frames, lambda: self.routes.handle('GET', '/api/v1/robots/table/state', self.read_authorization)[1]['joint_positions'])
        self.reinforcement = ReinforcementAPI(Path(__file__).resolve().parents[3] / 'data/reinforcement_api',
            limits, self.frames, self.routes, self.read_authorization)
        from ..vision.api import TextVisionAPI
        self.vision = TextVisionAPI(self.frames, self.reinforcement.jobs, self.reinforcement.onnx)
        core = Path(__file__).resolve().parents[3]
        self.hardware = HardwareControlAPI(core)
        from ..sim2real.service import Sim2RealAPI
        self.sim2real = Sim2RealAPI(core,self.hardware)
        from ..collection.playback import RecordingPlaybackAPI
        self.playback = RecordingPlaybackAPI(core / 'data/recordings', core / 'data/playbacks', limits,
            self.playback_reference, self.playback_apply)
        self.collection = CollectionAPI(core / 'data/collection_api', core, frames=self.frames, playback=self.playback)
        self.imitation.collection_resolver = self.collection.resolve_dataset
        super().__init__(("127.0.0.1", 8766), ModelRequestHandler)

    def playback_reference(self):
        if any(job['status'] in ('queued', 'running') for job in self.reinforcement.jobs.list()):
            raise ValueError('请先停止或等待强化学习训练/推理结束，再播放录制')
        status, state = self.routes.handle('GET', '/api/v1/robots/table/state', self.read_authorization)
        if status != 200:
            raise ValueError('无法读取 table 仿真模型')
        return state['joint_positions']

    def playback_apply(self, positions):
        status, receipt = self.routes.handle('POST', '/api/v1/robots/table/motions', self.read_authorization,
            {'request_id': str(uuid4()), 'expires_at_ms': time_ns() // 1000000 + 1000,
             'unit': 'rad', 'joint_positions': positions})
        if status not in (200, 202):
            raise ValueError(receipt.get('error', '仿真播放失败'))
        return receipt

    def server_close(self):
        self.programs.close()
        self.hardware.close()
        self.collection.close()
        self.reinforcement.close()
        self.imitation.close()
        self.frames.close()
        super().server_close()


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

    def _learning(self, method, body=None):
        for service in (self.server.hardware, self.server.programs, self.server.imitation, self.server.reinforcement, self.server.collection, self.server.blocks, self.server.vision, self.server.sim2real):
            if not self.path.startswith(service.prefix + '/'):
                continue
            if not compare_digest(self.headers.get('Authorization', '').encode(), self.server.read_authorization.encode()):
                self._reply(401, {'error': 'unauthorized'})
            else:
                self._reply(*service.handle(method, self.path, body))
            return True
        return False

    def do_GET(self) -> None:
        if self._learning('GET'):
            return
        if self.path == '/api/v1/cameras' or (self.path.startswith('/api/v1/cameras/') and self.path.endswith('/frame') and len(self.path.split('/')) == 6):
            if not compare_digest(self.headers.get('Authorization', '').encode(), self.server.read_authorization.encode()):
                self._reply(401, {'error': 'unauthorized'})
                return
            try:
                self._reply(200, self.server.frames.devices() if self.path == '/api/v1/cameras' else self.server.frames.read(self.path.split('/')[4]))
            except (ValueError, ImportError, OSError) as error:
                self._reply(409, {'error': str(error)})
            return
        # 仅模型状态允许本机匿名读取；运动写入始终要求令牌。
        if self.path != "/api/v1/robots/table/state":
            self._reply(404, {"error": "route_not_found"})
            return
        status, body = self.server.routes.handle("GET", self.path, self.server.read_authorization)
        self._reply(status, {**body, "source": "display_target", "physical": False, "camera": self.server.camera.snapshot(), "playback": self.server.playback.snapshot()})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= (1500000 if self.path == "/api/v1/cameras/virtual/frame" else 1000000 if self.path.startswith(("/api/v1/blocks/", "/api/v1/programs/")) else 16384):
                self._reply(413, {"error": "body_size_invalid"})
                return
            if self.headers.get_content_type() != "application/json":
                self._reply(415, {"error": "json_required"})
                return
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("对象必需")
        except (ValueError, UnicodeDecodeError):
            self._reply(400, {"error": "invalid_json"})
            return
        if self._learning('POST', body):
            return
        if self.path in ('/api/v1/cameras/virtual/frame', '/api/v1/cameras/real/config'):
            if not compare_digest(self.headers.get('Authorization', '').encode(), self.server.read_authorization.encode()):
                self._reply(401, {'error': 'unauthorized'})
                return
            try:
                result = (self.server.frames.publish(body) if self.path.endswith('/frame')
                          else self.server.frames.configure_real(body))
                self._reply(200, result)
            except (ValueError, KeyError, TypeError, OSError) as error:
                self._reply(422, {'error': str(error)})
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
    limits = JointLimits.from_urdf(root / "table/public/robots/so100/so100_mid_calib.urdf")
    with ModelHTTPServer(token, limits) as server:
        print("table 模型运动 API: http://127.0.0.1:8766；不连接实机", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

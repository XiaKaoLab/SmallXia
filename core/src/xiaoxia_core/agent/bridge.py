"""为 Tauri 提供单请求 JSONL 桥接，复用会话、技能与 Agent 流。
Created on 2026-11-01; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""

import json
import os
import sys
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from ..environment import EnvironmentSettings


class DesktopBridge:
    def __init__(self, directory: Path) -> None:
        global LLMConfig, OpenAILLM, SimpleAgent
        from ..llm import LLMConfig, OpenAILLM
        from .runtime import SimpleAgent
        from .sessions import SessionStore
        from .skills import SkillRegistry
        EnvironmentSettings.load()
        self.sessions = SessionStore(directory / "data" / "agent.sqlite3")
        self.skills = SkillRegistry(directory / "skills")

    @staticmethod
    def emit(event: dict) -> None:
        print(json.dumps(event, ensure_ascii=False), flush=True)

    def handle(self, request: dict) -> None:
        action = request.get("action")
        if action == "bootstrap":
            sessions = []
            for session_id in self.sessions.list_sessions():
                messages = self.sessions.read(session_id).messages
                title = messages[0].content[:48] if messages else "新对话"
                sessions.append({"id": session_id, "title": title})
            self.emit({"type": "data", "data": {
                "sessions": sessions,
                "skills": [{"name": skill.name, "description": skill.description}
                           for skill in self.skills.list()],
                "model": os.environ.get("OPENAI_MODEL", ""),
                "configured": bool(os.environ.get("OPENAI_MODEL") and os.environ.get("OPENAI_API_KEY")),
            }})
        elif action == "create":
            self.emit({"type": "data", "data": {"id": self.sessions.create()}})
        elif action == "history":
            snapshot = self.sessions.read(request["session_id"])
            self.emit({"type": "data", "data": {
                "messages": [asdict(message) for message in snapshot.messages]
            }})
        elif action == "clear":
            self.sessions.clear(request["session_id"])
            self.emit({"type": "data", "data": {"cleared": True}})
        elif action == 'alignment_preview':
            from ..communication.display_alignment import DisplayAlignment
            DisplayAlignment.stream(request.get('session_id'), self.emit)
        elif action == 'alignment_stop':
            from ..communication.display_alignment import DisplayAlignment
            self.emit({'type': 'data', 'data': DisplayAlignment.stop(request.get('session_id'))})
        elif action == 'reinforcement_preview':
            from ..reinforcement.preview import TrainingPreviewStream
            TrainingPreviewStream(Path(__file__).resolve().parents[3] / 'data/reinforcement_api/jobs').run(self.emit)
        elif action in ('reinforcement_jobs', 'reinforcement_job', 'reinforcement_stop', 'reinforcement_models', 'reinforcement_pause', 'reinforcement_resume'):
            from ..reinforcement.client import ReinforcementClient
            from ..imitation.api_jobs import identifier
            client = ReinforcementClient()
            if action == 'reinforcement_models':
                result = client.request('models')
            elif action == 'reinforcement_jobs':
                result = client.request('jobs')
            elif action == 'reinforcement_pause':
                result = client.pause_job(identifier(request.get('job_id')))
            elif action == 'reinforcement_resume':
                result = client.resume_job(identifier(request.get('job_id')))
            elif action == 'reinforcement_job':
                result = client.job(identifier(request.get('job_id')))
            else:
                result = client.stop_job(identifier(request.get('job_id')))
            self.emit({'type': 'data', 'data': result})
        elif action in ('blocks_poll', 'blocks_reply'):
            from urllib.request import Request, urlopen
            endpoint = 'poll' if action == 'blocks_poll' else 'replies'
            body = {key: value for key, value in request.items() if key != 'action'}
            query = Request('http://127.0.0.1:8766/api/v1/blocks/' + endpoint,
                data=json.dumps(body, allow_nan=False).encode(),
                headers={'Content-Type': 'application/json',
                         'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']}, method='POST')
            with urlopen(query, timeout=5) as response:
                self.emit({'type': 'data', 'data': json.load(response)})
        elif action == 'list_arm_ports':
            from serial.tools.list_ports import comports
            ports = sorted({port.device for port in comports()}, key=lambda value: (len(value), value))
            self.emit({'type': 'data', 'data': {'ports': ports, 'opened': False}})
        elif action == "list_cameras":
            from urllib.request import Request, urlopen
            query = Request('http://127.0.0.1:8766/api/v1/cameras',
                            headers={'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
            with urlopen(query, timeout=4) as response:
                self.emit({'type': 'data', 'data': json.load(response)})
        elif action == "publish_camera_frame":
            from urllib.request import Request, urlopen
            body = json.dumps({'image_base64': request['image_base64']}).encode()
            if len(body) > 1500000:
                raise ValueError('画面过大')
            upload = Request('http://127.0.0.1:8766/api/v1/cameras/virtual/frame', data=body,
                             headers={'Content-Type': 'application/json',
                                      'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']}, method='POST')
            with urlopen(upload, timeout=2) as response:
                self.emit({'type': 'data', 'data': json.load(response)})
        elif action == "run_program":
            from ..communication.program_runner import PythonProgramRunner
            self.emit({"type": "data", "data": PythonProgramRunner().run(request.get("source"))})
        elif action == "run":
            with OpenAILLM(LLMConfig.from_env(), enable_mcp=True) as llm:
                agent = SimpleAgent(llm, self.sessions, self.skills)
                with closing(agent.stream(
                    request["session_id"], request["text"],
                    skill_names=request.get("skill_names", []),
                )) as events:
                    for event in events:
                        self.emit(asdict(event))
        else:
            raise ValueError("未知桌面请求")


def main() -> None:
    # Windows 管道默认编码不一定是 UTF-8，与 Rust/前端明确统一。
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        request = json.loads(sys.stdin.readline())
        if not isinstance(request, dict):
            raise ValueError("桌面请求必须为对象")
        if request.get('action') in ('alignment_map', 'alignment_preview', 'alignment_stop', 'arm_calibration_action', 'alignment_recalibrate'):
            from ..communication.display_alignment import DisplayAlignment
            if request['action'] == 'alignment_recalibrate':
                DesktopBridge.emit({'type': 'data', 'data': DisplayAlignment.start(request.get('port'), recalibrate=True)})
            elif request['action'] == 'arm_calibration_action':
                DesktopBridge.emit({'type': 'data', 'data': DisplayAlignment.calibration_action(request.get('session_id'), request.get('stage'), request.get('index'))})
            elif request['action'] == 'alignment_preview':
                DisplayAlignment.stream(request.get('session_id'), DesktopBridge.emit)
            elif request['action'] == 'alignment_map':
                DesktopBridge.emit({'type': 'data', 'data': DisplayAlignment.start_mapping(request.get('port'))})
            else:
                DesktopBridge.emit({'type': 'data', 'data': DisplayAlignment.stop(request.get('session_id'))})
        elif request.get('action') in ('camera_calibration_action', 'camera_calibration_preview'):
            from ..communication.camera_calibration import CameraCalibration
            service = CameraCalibration()
            if request['action'] == 'camera_calibration_preview':
                service.stream(request.get('session_id'), DesktopBridge.emit)
            else:
                operation = request.get('operation')
                if operation not in ('start', 'get', 'capture', 'solve'):
                    raise ValueError('未知相机标定操作')
                if operation == 'start':
                    result = service.start(request.get('camera_id'), request.get('columns', 9), request.get('rows', 6), request.get('square_mm', 25))
                else:
                    result = getattr(service, operation)(request.get('session_id'))
                DesktopBridge.emit({'type': 'data', 'data': result})
        elif request.get('action') in ('reinforcement_pause', 'reinforcement_resume'):
            from ..reinforcement.client import ReinforcementClient
            from ..imitation.api_jobs import identifier
            client = ReinforcementClient()
            operation = client.pause_job if request['action'] == 'reinforcement_pause' else client.resume_job
            from time import monotonic, sleep
            job_id = identifier(request.get('job_id'))
            result = operation(job_id)
            target = request['action'] == 'reinforcement_pause'
            deadline = monotonic() + .5
            while bool(result.get('paused')) != target and result['status'] in ('queued', 'running') and monotonic() < deadline:
                sleep(.005)
                result = client.job(job_id)
            DesktopBridge.emit({'type': 'data', 'data': result})
        else:
            DesktopBridge(Path.cwd()).handle(request)
    except Exception as error:
        DesktopBridge.emit({"type": "error", "message": str(error)})
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

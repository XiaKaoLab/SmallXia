"""采集 API 客户端：会话、命令回执与成功完成的数据集结果。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class CollectionClient:
    def request(self, endpoint, body=None):
        request = Request('http://127.0.0.1:8766/api/v1/collection/' + endpoint,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['XIAOXIA_MOTION_TOKEN']})
        try:
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
                from ..blocks.workflow import BlockWorkflow
                BlockWorkflow.track_created('collection', endpoint, body, result)
                return result
        except HTTPError as error:
            raise RuntimeError(json.loads(error.read()).get('error', str(error))) from None

    def create_simulation(self, task, fps=10, cameras=None, **options):
        return self.request('simulation/sessions', {'task': task, 'fps': fps, 'cameras': cameras or [], **options})

    def create_hardware(self, task, profile, fps=10, cameras=None, *, read_only_confirmed=False, **options):
        return self.request('hardware/sessions', {'task': task, 'profile': profile, 'fps': fps,
                            'cameras': cameras or [], 'read_only_confirmed': read_only_confirmed, **options})

    def start(self, session_id):
        return self.request(f'sessions/{session_id}/start', {})

    def record(self, session_id, duration_s=10, action=None):
        return self.request(f'sessions/{session_id}/record', {'duration_s': duration_s, **({'action': action} if action is not None else {})})

    def capture(self, session_id, action=None):
        return self.request(f'sessions/{session_id}/frames', {} if action is None else {'action': action})

    def save_episode(self, session_id):
        return self.request(f'sessions/{session_id}/episodes', {})

    def finish(self, session_id):
        return self.request(f'sessions/{session_id}/finish', {})

    def stop(self, session_id):
        return self.request(f'sessions/{session_id}/stop', {})

    def session(self, session_id):
        return self.request(f'sessions/{session_id}')

    def command(self, session_id, command_id):
        return self.request(f'sessions/{session_id}/commands/{command_id}')

    def recordings(self):
        return self.request('recordings')

    def play(self, recording_id='latest_motion', speed=1, reference=None, directions=None):
        return self.request('playbacks', {'recording_id': recording_id, 'speed': speed,
            **({'reference': reference} if reference is not None else {}),
            **({'directions': directions} if directions is not None else {})})

    def playback(self, playback_id):
        return self.request(f'playbacks/{playback_id}')

    def pause_playback(self, playback_id):
        return self.request(f'playbacks/{playback_id}/pause', {})

    def resume_playback(self, playback_id):
        return self.request(f'playbacks/{playback_id}/resume', {})

    def stop_playback(self, playback_id):
        return self.request(f'playbacks/{playback_id}/stop', {})

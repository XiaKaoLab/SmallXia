"""组合通信和记录器，按调用方节拍采集单帧，不主动发送动作。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from ..communication import RobotTransport
from ..contracts import Action, Observation
from .recorder import EpisodeRecorder


class CollectionService:
    def __init__(self, transport: RobotTransport, recorder: EpisodeRecorder) -> None:
        self._transport = transport
        self._recorder = recorder

    def capture(self, demonstrated_action: Action | None = None) -> Observation:
        observation = self._transport.read_observation()
        self._recorder.append(observation, demonstrated_action)
        return observation

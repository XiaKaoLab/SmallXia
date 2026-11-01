"""采集模块公共接口。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from .recorder import EpisodeRecorder
from .service import CollectionService

__all__ = ["CollectionService", "EpisodeRecorder"]

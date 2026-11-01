"""封装 LeRobot 原生数据集入口，按需加载训练依赖。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lerobot.datasets.lerobot_dataset import LeRobotDataset


class LeRobotDatasets:
    @staticmethod
    def open(repo_id: str, root: Path) -> "LeRobotDataset":
        """读取已有本地数据集，不自动下载视频。"""
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        if not root.is_dir():
            raise FileNotFoundError(root)
        return LeRobotDataset(repo_id=repo_id, root=root, download_videos=False)

    @staticmethod
    def create(
        repo_id: str,
        root: Path,
        fps: int,
        features: dict[str, dict[str, Any]],
        robot_type: str = "so101_follower",
    ) -> "LeRobotDataset":
        """创建 LeRobot 原生数据集；调用方负责 add_frame/save_episode。"""
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        if fps < 1:
            raise ValueError("fps 必须大于零")
        if root.exists():
            raise FileExistsError(root)
        return LeRobotDataset.create(
            repo_id=repo_id, root=root, fps=fps, features=features, robot_type=robot_type
        )

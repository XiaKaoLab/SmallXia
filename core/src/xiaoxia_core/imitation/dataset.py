"""记录实际主从控制目标为 LeRobot v3 数据集，保留弧度和仿真来源。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image

from ..contracts import Action, Observation
from ..safety import JOINTS, JointLimits


class DemonstrationWriter:
    def __init__(self, root: Path, repo_id: str, fps: int, limits: JointLimits, first_observation: Observation, *, simulated: bool, robot_type: str = "so100_follower") -> None:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        if root.exists() or fps < 1:
            raise ValueError("数据集目录必须尚不存在，fps 必须为正数")
        self.limits = limits
        self.images: dict[str, tuple[int, ...]] = {}
        features = {key: {"dtype": "float32", "shape": (6,), "names": list(JOINTS)}
                    for key in ("observation.state", "action")}
        for name, path in first_observation.image_paths.items():
            with Image.open(path) as image:
                self.images[name] = np.asarray(image.convert("RGB")).shape
            features[f"observation.images.{name}"] = {"dtype": "image", "shape": self.images[name], "names": ["height", "width", "channels"]}
        if not self.images:
            # ACT 无图像时需要 environment_state；这里只提供同一状态的副本，不引入未来目标。
            features["observation.environment_state"] = features["observation.state"].copy()
        self.dataset = LeRobotDataset.create(repo_id=repo_id, root=root, fps=fps, features=features, robot_type=robot_type, use_videos=False)
        self.frames = 0
        self.metadata = {
            "schema_version": 1, "joints": list(JOINTS), "unit": "radian", "simulated": simulated,
            "observation_mode": "images" if self.images else "state_only",
            "environment_state": None if self.images else "duplicate_of_observation.state",
            "limits": {name: asdict(limit) for name, limit in limits.joints.items()},
            "images": {name: list(shape) for name, shape in self.images.items()},
            "fps": fps, "repo_id": repo_id,
        }
        (root / "imitation.json").write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    def append(self, observation: Observation, action: Action, task: str) -> None:
        self.limits.validate(observation.joint_positions)
        self.limits.validate(action.joint_positions)
        if set(observation.image_paths) != set(self.images):
            raise ValueError("相机帧与数据集特征不匹配")
        frame = {
            "observation.state": np.array([observation.joint_positions[name] for name in JOINTS], dtype=np.float32),
            "action": np.array([action.joint_positions[name] for name in JOINTS], dtype=np.float32),
            "task": task,
        }
        if not self.images:
            frame["observation.environment_state"] = frame["observation.state"].copy()
        for name, path in observation.image_paths.items():
            with Image.open(path) as image:
                pixels = np.asarray(image.convert("RGB"))
            if pixels.shape != self.images[name]:
                raise ValueError("相机分辨率在 episode 中变化")
            frame[f"observation.images.{name}"] = pixels
        self.dataset.add_frame(frame)
        self.frames += 1

    def save_episode(self) -> None:
        if self.frames < 2:
            raise ValueError("一个 episode 至少需要两帧")
        self.dataset.save_episode()
        self.frames = 0

    def close(self) -> None:
        self.dataset.finalize()

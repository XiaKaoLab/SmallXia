"""组织仿真主从、实机示教记录和策略回放，保持前端独立。
Created on 2026-11-01; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""

from math import isfinite, sin
from pathlib import Path
from time import monotonic, sleep

import yaml

from ..collection.cameras import CameraTransport
from ..communication.calibration import ArmCalibration
from ..communication.so_arm import SOArmTransport
from ..safety import JOINTS, JointLimits
from ..simulation import MujocoSimulation, SimulationConfig
from .act import ACTJointPolicy
from .dataset import DemonstrationWriter
from .pair import LeaderFollowerPair
from .keyboard import KeyboardLeader


class SimulationWorkflow:
    def __init__(self, urdf: Path, fps: int = 30) -> None:
        if not 1 <= fps <= 120:
            raise ValueError("fps 必须在 1–120 之间")
        self.urdf, self.fps = urdf, fps
        self.limits = JointLimits.from_urdf(urdf)

    def record(self, root: Path, repo_id: str, frames: int = 60, episodes: int = 2) -> dict:
        if frames < 2 or episodes < 1:
            raise ValueError("需要至少两帧和一个 episode")
        config = SimulationConfig(self.urdf, timestep=1 / (self.fps * 10), max_velocity=0.25)
        leader, follower = MujocoSimulation(config), MujocoSimulation(config)
        peak_speed = peak_error = 0.0
        with LeaderFollowerPair(leader, follower, self.limits, self.fps) as pair:
            midpoint = self.limits.midpoint()
            leader.set_kinematic_pose(midpoint)
            follower.set_kinematic_pose(midpoint)
            writer = DemonstrationWriter(root, repo_id, self.fps, self.limits, follower.read_observation(), simulated=True)
            try:
                for episode in range(episodes):
                    follower.set_kinematic_pose(midpoint)
                    for frame in range(frames):
                        phase = frame / self.fps
                        desired = {name: midpoint[name] + 0.06 * sin(phase * 0.7 + episode * 0.2) for name in JOINTS}
                        leader.set_kinematic_pose(desired)
                        observation, action = pair.capture()
                        writer.append(observation, action, "simulated bounded leader follower trajectory")
                        for _ in range(10):
                            state = follower.step()
                            self.limits.validate(state.joint_positions, tolerance=1e-4)
                            diagnostics = follower.diagnostics()
                            peak_speed = max(peak_speed, *(abs(value) for value in diagnostics["joint_velocities"].values()))
                            if any(abs(value) > self.limits.joints[name].velocity + 1e-4 for name, value in diagnostics["joint_velocities"].items()):
                                raise RuntimeError("仿真实际关节速度超出模型上限")
                        peak_error = max(peak_error, *(abs(state.joint_positions[name] - desired[name]) for name in JOINTS))
                    writer.save_episode()
            finally:
                writer.close()
        return {"simulated": True, "leader_mode": "scripted_kinematic_input", "follower_mode": "mujoco_dynamics",
                "episodes": episodes, "frames": frames * episodes, "peak_speed_rad_s": peak_speed,
                "peak_tracking_error_rad": peak_error, "physical_limits_verified": False, "dataset": str(root)}

    def rollout(self, checkpoint: Path, frames: int = 30) -> dict:
        if frames < 1:
            raise ValueError("回放帧数必须为正数")
        policy = ACTJointPolicy()
        policy.load(checkpoint)
        if not policy.metadata["simulated"]:
            raise ValueError("当前仿真回放仅接受明确标注的仿真数据检查点")
        peak_speed = 0.0
        with MujocoSimulation(SimulationConfig(self.urdf, timestep=1 / (self.fps * 10))) as follower:
            follower.set_kinematic_pose(self.limits.midpoint())
            for _ in range(frames):
                observation = follower.read_observation()
                action = policy.predict(observation)
                safe_action = self.limits.constrain(action, observation.joint_positions, 1 / self.fps, 0.25)
                follower.send_action(safe_action)
                for _ in range(10):
                    self.limits.validate(follower.step().joint_positions, tolerance=1e-4)
                    velocities = follower.diagnostics()["joint_velocities"]
                    peak_speed = max(peak_speed, *(abs(value) for value in velocities.values()))
                    if any(abs(value) > self.limits.joints[name].velocity + 1e-4 for name, value in velocities.items()):
                        raise RuntimeError("策略回放实际速度超出模型上限")
            return {"simulated": True, "frames": frames, "completed": True,
                    "peak_speed_rad_s": peak_speed,
                    "task_success_validated": False, "positions": follower.read_observation().joint_positions}


class HardwareWorkflow:
    def __init__(self, profile: Path) -> None:
        self.directory = profile.resolve().parent
        self.config = yaml.safe_load(profile.read_text(encoding="utf-8"))
        if self.config.get("device_identity_confirmed") is not True:
            raise ValueError("先由操作者确认两臂设备身份及主从端口，再设置 device_identity_confirmed=true")
        if self.config.get("robot") not in ("so100", "so101"):
            raise ValueError("仅支持 SO-100/101 配置")
        self.limits = JointLimits.from_urdf(self.path(self.config["urdf"]))
        self.fps = self.config.get("fps", 30)
        if not 1 <= self.fps <= 60:
            raise ValueError("实机 fps 必须在 1–60 之间")

    def path(self, value: str) -> Path:
        if not value:
            raise ValueError("请填写实际路径，不能使用空的示例配置")
        return (self.directory / value).resolve()

    def arm(self, role: str) -> SOArmTransport:
        item = self.config[role]
        if self.config.get('coordinate_basis')=='official_calibration':
            from ..communication.official_control import OfficialArmCalibration
            calibration=OfficialArmCalibration(self.path(item['calibration']),self.path(item['zero_reference']) if item.get('zero_reference') else None)
        else:
            calibration = ArmCalibration.load(self.path(item["calibration"]), self.path(item["mapping"]), self.limits)
        return SOArmTransport(item["port"], calibration, role,
                              max_velocity=self.config.get("max_velocity_rad_s", 0.25), identity_confirmed=True,
                              pid_compensation=item.get('pid_load_compensation'),
                                software_pid_enabled=item.get('software_pid_enabled', True),
                                trajectory_mode=item.get('trajectory_mode', 'servo'))

    def inspect(self) -> dict:
        follower = self.arm("follower")
        with follower:
            return {"simulated": False, "writes": 0, "torque_enabled_by_this_run": False,
                    "follower": follower.read_observation().joint_positions}

    def record(self, root: Path | None, repo_id: str, seconds: float, episodes: int, *, motion_enabled: bool) -> dict:
        if not motion_enabled:
            raise ValueError("实机运动需要显式 --enable-motion --workspace-clear")
        if not isfinite(seconds) or seconds <= 0 or episodes < 1 or round(seconds * self.fps) < (2 if root is not None else 1):
            raise ValueError("时长和 episode 数必须为正数")
        raw_follower = self.arm("follower")
        follower = raw_follower
        cameras = self.config.get("cameras", {})
        if cameras:
            follower = CameraTransport(raw_follower, cameras, self.directory.parent / "data" / "camera_frames")
        kind = self.config.get("leader", {}).get("kind", "hardware")
        if kind not in ("keyboard", "hardware"):
            raise ValueError("leader.kind 必须为 keyboard 或 hardware")
        leader = KeyboardLeader(follower, raw_follower.limits) if kind == "keyboard" else self.arm("leader")
        writer = None
        total = 0
        with LeaderFollowerPair(leader, follower, raw_follower.limits, self.fps) as pair:
            try:
                if root is not None:
                    writer = DemonstrationWriter(root, repo_id, self.fps, raw_follower.limits, follower.read_observation(), simulated=False, robot_type=f"{self.config['robot']}_follower")
                for episode in range(episodes):
                    raw_follower.arm()
                    deadline = monotonic()
                    for _ in range(round(seconds * self.fps)):
                        observation, action = pair.capture()
                        if writer:
                            writer.append(observation, action, self.config.get("task", "SO arm demonstration"))
                        total += 1
                        deadline += 1 / self.fps
                        sleep(max(0, deadline - monotonic()))
                    # 保存数据可能很慢，先释放从臂力矩；要求机械臂由操作者安全支撑。
                    raw_follower.disconnect()
                    if writer:
                        writer.save_episode()
                    if episode != episodes - 1:
                        raw_follower.connect()
            finally:
                if writer:
                    writer.close()
        return {"simulated": False, "frames": total, "episodes": episodes, "recorded": writer is not None}

    def rollout(self, checkpoint: Path, seconds: float, *, motion_enabled: bool) -> dict:
        if not motion_enabled or not isfinite(seconds) or seconds <= 0 or round(seconds * self.fps) < 1:
            raise ValueError("实机推理需要正时长及显式动作授权")
        policy = ACTJointPolicy()
        policy.load(checkpoint)
        if policy.metadata["simulated"]:
            raise ValueError("拒绝把仅用仿真数据训练的检查点直接发送给实机")
        raw = self.arm("follower")
        follower = raw
        if self.config.get("cameras"):
            follower = CameraTransport(raw, self.config["cameras"], self.directory.parent / "data" / "camera_frames")
        frames = round(seconds * self.fps)
        with follower:
            raw.arm()
            deadline = monotonic()
            for _ in range(frames):
                observation = follower.read_observation()
                raw.send_action(policy.predict(observation))
                deadline += 1 / self.fps
                sleep(max(0, deadline - monotonic()))
        return {"simulated": False, "frames": frames, "completed": True}

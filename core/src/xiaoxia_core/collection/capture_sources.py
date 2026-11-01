"""提供 MuJoCo 物理采集及只读实机采集源，图像与状态保留各自时间来源。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import base64
from pathlib import Path
from time import time_ns
from PIL import Image

from ..contracts import Observation
from .frame_client import CameraFrameClient


class SimulationCaptureSource:
    def __init__(self, config, core):
        from ..simulation import MujocoSimulation, SimulationConfig
        self.transport = MujocoSimulation(SimulationConfig(urdf_path=core / 'assets/so100/so100.urdf',
                                      timestep=1 / (config['fps'] * 10)))
        self.config = config
        self.renderer = None

    def connect(self):
        self.transport.connect()
        self.transport.set_kinematic_pose(self.transport.limits.midpoint())
        if self.config['cameras']:
            import mujoco
            model, _ = self.transport._state()
            self.renderer = mujoco.Renderer(model, height=240, width=320)

    def observation(self, directory, frame_index):
        observation = self.transport.read_observation()
        images = {}
        if self.renderer:
            import mujoco
            model, data = self.transport._state()
            camera = mujoco.MjvCamera()
            mujoco.mjv_defaultCamera(camera)
            camera.lookat[:] = [0, 0, 0.15]
            camera.distance, camera.azimuth, camera.elevation = 0.7, 135, -25
            self.renderer.update_scene(data, camera=camera)
            path = directory / f'{frame_index:08d}-simulation.png'
            Image.fromarray(self.renderer.render()).save(path)
            images['simulation'] = str(path)
        return Observation(observation.timestamp_ns, observation.joint_positions, images)

    def advance(self, action):
        if action is not None:
            self.transport.send_action(action)
        self.transport.step(10)
        return action

    def close(self):
        if self.renderer:
            self.renderer.close()
        self.transport.disconnect()


class HardwareCaptureSource:
    def __init__(self, config, core):
        from ..imitation.workflows import HardwareWorkflow
        self.workflow = HardwareWorkflow(core / 'configs' / config['profile'])
        self.transport = self.workflow.arm('follower')
        self.config = config
        self.client = CameraFrameClient()
        self._camera_opened = False

    def connect(self):
        self.transport.connect()  # 仅身份/校准校验和读取；不调用 arm()。

    def observation(self, directory, frame_index):
        observation = self.transport.read_observation()
        images, metadata = {}, {}
        for source in self.config['cameras']:
            frame = self.client.read(source)
            self._camera_opened = True
            path = directory / f'{frame_index:08d}-{source}.jpg'
            path.write_bytes(base64.b64decode(frame['image_base64']))
            images[source] = str(path)
            metadata[source] = {key: value for key, value in frame.items() if key != 'image_base64'}
        self.camera_metadata = metadata
        return Observation(observation.timestamp_ns, observation.joint_positions, images)

    def advance(self, action):
        # 动作仅是外部示教标签，此入口不控制实机。
        return action

    def close(self):
        try:
            self.transport.disconnect()
        finally:
            if self._camera_opened:
                self.client.configure_real(enabled=False)

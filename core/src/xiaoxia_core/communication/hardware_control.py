"""为已验证坐标配置的从臂提供显式使能、限速运动与失联释放，不自动改写校准。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from copy import deepcopy
from pathlib import Path
import re
from threading import Event, RLock, Thread
from time import monotonic

from ..contracts import Action
from ..imitation.workflows import HardwareWorkflow
from .model_pose_guard import ModelPoseGuard


class HardwareControlAPI:
    prefix = '/api/v1/hardware'

    def __init__(self, core):
        self.core = core
        self.sessions = {}
        self.lock = RLock()

    def handle(self, method, path, body=None):
        body = body or {}
        if method == 'GET' and path == self.prefix + '/arms':
            with self.lock:
                return 200, {'physical': True, 'sessions': [
                    session.snapshot() for session in self.sessions.values()
                ]}
        parts = path.removeprefix(self.prefix).strip('/').split('/')
        try:
            if len(parts) not in (2, 3) or parts[0] != 'arms' or not re.fullmatch(r'COM[1-9][0-9]*', parts[1]):
                raise ValueError('请选择 COM 口')
            port = parts[1]
            with self.lock:
                if method == 'POST' and len(parts) == 3 and parts[2] == 'connect':
                    if body.get('enable_motion') is not True:
                        raise ValueError('请勾选启用真机运动')
                    profile = body.get('profile', 'so100.local.yaml')
                    if not isinstance(profile, str) or Path(profile).name != profile or not profile.endswith('.yaml'):
                        raise ValueError('请选择本机机械臂配置')
                    if port in self.sessions and self.sessions[port].active:
                        raise ValueError('机械臂已在控制中')
                    workflow = HardwareWorkflow(self.core / 'configs' / profile)
                    expected = self.core.parent / 'table/public/robots/so100/so100_mid_calib.urdf'
                    if workflow.path(workflow.config['urdf']) != expected.resolve():
                        raise ValueError('真机控制配置需要使用当前 SO100 模型坐标')
                    arm = workflow.arm('follower')  # 强制 verified=true 与 EEPROM 匹配，不使用显示偏移。
                    if arm.port != port:
                        raise ValueError('配置中的从臂端口不匹配')
                    session = HardwareControlSession(arm, ModelPoseGuard(workflow.path(workflow.config['urdf'])))
                    self.sessions[port] = session
                    session.start()
                    return 202, session.snapshot()
                session = self.sessions.get(port)
                if session is None:
                    raise ValueError('请先连接真机控制')
                if method == 'GET' and len(parts) == 2:
                    return 200, session.snapshot(heartbeat=True)
                if method == 'POST' and len(parts) == 3 and parts[2] == 'stop':
                    session.stop.set()
                    return 202, session.snapshot()
                if method == 'POST' and len(parts) == 3 and parts[2] == 'motions':
                    return 202, session.move(body)
            return 404, {'error': 'route_not_found'}
        except (ValueError, KeyError, TypeError, OSError) as error:
            return 422, {'error': str(error)}

    def close(self):
        for session in self.sessions.values():
            session.stop.set()
        for session in self.sessions.values():
            session.thread.join(timeout=2)


class HardwareControlSession:
    def __init__(self, arm, guard):
        self.arm, self.guard = arm, guard
        self.stop, self.lock = Event(), RLock()
        self.lease = monotonic()
        self.target = None
        self.state = {'status': 'connecting', 'port': arm.port, 'physical': True, 'unit': 'rad'}
        self.thread = Thread(target=self.run, daemon=True)

    @property
    def active(self):
        return self.state['status'] in ('connecting', 'ready', 'moving')

    def start(self):
        self.thread.start()

    def snapshot(self, heartbeat=False):
        with self.lock:
            if heartbeat:
                self.lease = monotonic()
            return deepcopy(self.state)

    def move(self, body):
        with self.lock:
            if not self.active or self.state['status'] == 'connecting':
                raise ValueError('机械臂控制尚未就绪')
            if body.get('unit') != 'rad':
                raise ValueError('仅支持弧度')
            positions = body.get('joint_positions')
            self.arm.limits.validate(positions)
            applied, reason = self.guard.limit_path(self.state['joint_positions'], positions)
            self.target = dict(applied)
            self.state.update(status='moving', target=applied, limited=bool(reason))
            self.lease = monotonic()
            return deepcopy(self.state)

    def run(self):
        try:
            self.arm.connect()
            current = self.arm.read_observation().joint_positions
            self.guard.assert_pose(current)
            if self.stop.is_set():
                return
            self.arm.arm()
            with self.lock:
                self.target = current
                self.state.update(status='ready', joint_positions=current)
                self.lease = monotonic()
            while not self.stop.wait(1 / 30):
                with self.lock:
                    if monotonic() - self.lease > 2:
                        raise TimeoutError('控制连接已断开')
                    target = dict(self.target)
                self.arm.send_action(Action(target))
                measured = self.arm.read_observation().joint_positions
                reached = max(abs(measured[name] - target[name]) for name in target) < .025
                with self.lock:
                    self.state.update(joint_positions=measured, status='ready' if reached else 'moving')
        except Exception as error:
            with self.lock:
                self.state.update(status='failed', error=str(error))
        finally:
            try:
                self.arm.disconnect()
            finally:
                with self.lock:
                    if self.state['status'] != 'failed':
                        self.state['status'] = 'stopped'

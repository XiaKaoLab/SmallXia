"""复用 LeRobot Feetech 总线实现 SO-100/101 主从臂，连接时只读且不自动校准。
Created on 2026-11-01; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""

from math import isfinite, pi, radians
from time import monotonic, monotonic_ns

from ..contracts import Action, Observation
from ..safety import JOINTS
from .calibration import ArmCalibration
from .transport import RobotTransport
from .joint_trajectory import JointTrajectory
from .joint_pid import JointPID


class SOArmTransport(RobotTransport):
    def __init__(self, port: str, calibration: ArmCalibration, role: str, max_velocity: float = 0.25, timeout: float = 0.25, *, identity_confirmed: bool = False, pid_compensation=None, software_pid_enabled: bool = True, trajectory_mode='servo') -> None:
        if role not in ("leader", "follower") or not port:
            raise ValueError("需要明确主从角色和串口")
        if not all(isfinite(v) and v > 0 for v in (max_velocity, timeout)):
            raise ValueError("速度和通信超时必须为有限正数")
        self.port, self.calibration, self.role = port, calibration, role
        self.limits = calibration.limits
        self.max_velocity, self.timeout = max_velocity, timeout
        self.identity_confirmed = identity_confirmed
        JointPID.validate_compensation(pid_compensation, calibration.limits.joints)
        self.pid_compensation = pid_compensation
        if type(software_pid_enabled) is not bool:
            raise ValueError('软件外环开关必须为布尔值')
        self.software_pid_enabled = software_pid_enabled
        if trajectory_mode not in ('servo', 'software'): raise ValueError('未知运动轨迹模式')
        self.trajectory_mode = trajectory_mode
        self._servo_trajectory = None
        self._bus = None
        self._armed = False
        self._trajectory = None
        self._pid = None
        self._last_ticks = None
        self.render_joint_positions = None
        self._render_wrist_offset = 0.0
        self.release_feedback = None
        self.release_result = {}
        self._return_pose = None
        self._last_command: dict[str, float] | None = None
        self._last_sent = 0.0

    def connect(self) -> None:
        if not self.identity_confirmed:
            raise RuntimeError("需要操作者确认设备身份；电机响应或 USB 描述不能证明它是目标机械臂")
        from lerobot.motors import Motor, MotorCalibration, MotorNormMode
        from lerobot.motors.feetech import FeetechMotorsBus

        if self._bus is not None:
            raise RuntimeError("机械臂已连接")
        calibration = {name: MotorCalibration(joint.id, 0, joint.homing_offset, joint.range_min, joint.range_max)
                       for name, joint in self.calibration.joints.items()}
        bus = FeetechMotorsBus(self.port, motors={name: Motor(index, "sts3215", MotorNormMode.DEGREES)
                               for index, name in enumerate(JOINTS, 1)}, calibration=calibration)
        try:
            bus.connect()  # 官方总线握手仅 ping/读取固件，不调用机器人 configure/calibrate。
            bus.set_timeout(self.timeout * 1000)
            actual = bus.read_calibration()
            if actual != calibration:
                raise RuntimeError("电机 EEPROM 校准与文件不一致；拒绝自动改写")
            if any(bus.sync_read("Torque_Enable", normalize=False).values()):
                raise RuntimeError("连接前需将两臂安全支撑并解除力矩；当前只读连接不会更改力矩")
            if any(bus.read("Operating_Mode", name, normalize=False) != 0 for name in JOINTS):
                raise RuntimeError("电机未处于位置模式；拒绝自动改写")
            self._bus = bus
            if hasattr(self.calibration,'render_angles'):
                from .display_frame import DisplayFrame
                self._render_wrist_offset=DisplayFrame.load(self.port,self.calibration.raw_calibration)
            self.read_observation()
        except BaseException:
            self._bus = None
            if bus.is_connected:
                bus.disconnect(disable_torque=False)
            raise

    def _connected(self):
        if self._bus is None:
            raise RuntimeError("请先连接机械臂")
        return self._bus

    def read_observation(self) -> Observation:
        ticks = self._connected().sync_read("Present_Position", normalize=False)
        positions = self.calibration.angles(ticks)
        self.render_joint_positions=self.render_positions(positions)
        return Observation(monotonic_ns(), positions)

    def render_positions(self,positions):
        if hasattr(self.calibration,'render_angles'):
            from .display_frame import DisplayFrame
            return DisplayFrame.apply(self.calibration.render_angles(positions),self._render_wrist_offset)
        return dict(positions)

    def control_positions(self, positions, current):
        """将策略的模型绝对角度转回编码器控制坐标，复用显示转换的逆变换。"""
        if set(positions) != set(JOINTS) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v) for v in positions.values()):
            raise ValueError('策略必须给出六轴有限角度')
        if not hasattr(self.calibration, 'render_angles'):
            return dict(positions)
        result = {name: positions[name] - self.calibration.render_offsets[name] for name in JOINTS}
        result['wrist_roll'] -= radians(self._render_wrist_offset)
        limits = self.limits.joints['wrist_roll']
        current = current['wrist_roll']
        candidates = [result['wrist_roll'] + turns * 2 * pi for turns in range(-2, 3)]
        candidates = [value for value in candidates if limits.lower <= value <= limits.upper]
        if not candidates: raise ValueError('腕部策略目标超出实机行程')
        result['wrist_roll'] = min(candidates, key=lambda value: abs(value - current))
        self.limits.validate(result)
        return result

    def arm(self) -> None:
        if self.role != "follower":
            raise RuntimeError("主臂只读，禁止力矩使能")
        bus = self._connected()
        current = self.read_observation().joint_positions
        self._return_pose=dict(current)
        if self.trajectory_mode == 'servo':
            from .servo_trajectory import ServoTrajectory
            self._servo_trajectory = ServoTrajectory(bus, self.calibration)
        ticks = self.calibration.ticks(current)
        bus.sync_write("Goal_Position", ticks, normalize=False)
        if bus.sync_read("Goal_Position", normalize=False) != ticks:
            raise RuntimeError("使能前目标寄存器未确认，禁止启动力矩")
        self._armed = True  # 使能中途异常时 disconnect 也必须释放已启用的轴。
        try:
            bus.enable_torque()
            enabled = bus.sync_read("Torque_Enable", normalize=False)
            if set(enabled) != set(JOINTS) or not all(enabled.values()):
                raise RuntimeError("从臂力矩使能回读不完整")
            self._last_command, self._last_sent = dict(current), monotonic()
            self._trajectory=JointTrajectory(current,self.max_velocity)
            self._pid=JointPID(current,self.max_velocity,compensation=self.pid_compensation) if self.software_pid_enabled and self.trajectory_mode == 'software' else None
            self._last_ticks=dict(ticks)
        except BaseException:
            self.disconnect()
            raise

    def send_action(self, action: Action, *, max_velocity=None) -> None:
        if self.role != "follower" or not self._armed:
            raise RuntimeError("从臂尚未显式使能")
        bus = self._connected()
        try:
            now = monotonic()
            elapsed = now - self._last_sent
            if elapsed > self.timeout:
                raise RuntimeError("控制周期超时，拒绝继续动作")
            current = self.read_observation().joint_positions
            dt = min(elapsed, 1 / 30)
            self.limits.validate(action.joint_positions)
            if self._servo_trajectory:
                speed = self.max_velocity if max_velocity is None else min(self.max_velocity, max_velocity)
                self._servo_trajectory.send(action.joint_positions, speed)
                self._last_ticks = self.calibration.ticks(action.joint_positions)
                self._last_command = dict(action.joint_positions)
                self._last_sent = now
                return
            if self._trajectory is None:self._trajectory=JointTrajectory(current,self.max_velocity)
            speed = self.max_velocity if max_velocity is None else min(self.max_velocity, max_velocity)
            if not isfinite(speed) or speed <= 0: raise ValueError('运动速度无效')
            self._trajectory.speed = speed
            if self.software_pid_enabled and self._pid is None:self._pid=JointPID(current,speed,compensation=self.pid_compensation)
            target=self._pid.target(action.joint_positions) if self._pid else action.joint_positions
            reference=self._trajectory.step(target,max(dt,.0001))
            pose=self._pid.step(reference,current,max(dt,.0001),speed) if self._pid else reference
            # 修正不可越过已确认行程；从行程外起步时保留平滑恢复轨迹。
            pose={name:max(min(reference[name],self.limits.joints[name].lower),
                  min(max(reference[name],self.limits.joints[name].upper),value)) for name,value in pose.items()}
            ticks = self.calibration.ticks(pose)
            if ticks!=self._last_ticks:
                bus.sync_write("Goal_Position", ticks, normalize=False)
                self._last_ticks=dict(ticks)
            # 内部保留浮点累积，不能每周期量化后重新起步。
            self._last_command=pose
            self._last_sent = now
        except BaseException:
            self.disconnect()
            raise

    @property
    def applied_action(self) -> Action:
        if self._last_command is None:
            raise RuntimeError("尚无已发送目标")
        return Action(dict(self._last_command))

    @property
    def control_diagnostics(self):
        return {'stabilizer':'servo_profile' if self._servo_trajectory else 'pid_deadband' if self.software_pid_enabled else 'trajectory_only',
                'trajectory_mode': self.trajectory_mode,
                'servo_goal_writes': self._servo_trajectory.goal_writes if self._servo_trajectory else 0,
                'servo_speed_registers': self._servo_trajectory.speed_registers if self._servo_trajectory else {},
                'software_pid_enabled':self.software_pid_enabled and self.trajectory_mode == 'software',
                'last_sent_goal_ticks':dict(self._last_ticks or {}),
                'pid_load_compensation':(self.pid_compensation or {}) if self.software_pid_enabled else {},
                'pid_moving_joints':[name for name,moving in self._pid.moving.items() if moving] if self._pid else [],
                'pid_holding_joints':[name for name,locked in self._pid.locked.items() if locked] if self._pid else []}

    def disconnect(self) -> None:
        bus, self._bus = self._bus, None
        try:
            if bus is not None and bus.is_connected:
                try:
                    if self._armed:
                        from .slow_zero_release import SlowZeroRelease
                        try:
                            self.release_result=SlowZeroRelease(self.calibration,self.max_velocity,self.release_feedback,target=self._return_pose,pid_compensation=self.pid_compensation,software_pid_enabled=self.software_pid_enabled,servo_trajectory=self._servo_trajectory).run(bus)
                        except Exception as error:
                            self.release_result={'zero_reached':False,'error':str(error)}
                            raise
                        finally:
                            # 异常也逐项记录；故障时不能谎报已回零。
                            bus.sync_write("Torque_Enable", {name:0 for name in JOINTS}, normalize=False)
                            torque=bus.sync_read("Torque_Enable", normalize=False)
                            self.release_result['torque_disabled']=not any(torque.values())
                            if any(torque.values()):raise RuntimeError("部分电机力矩尚未关闭")
                finally:
                    try:
                        if self._servo_trajectory and not any(bus.sync_read('Torque_Enable', normalize=False).values()):
                            self._servo_trajectory.restore()
                    finally:
                        bus.disconnect(disable_torque=False)
        finally:
            self._armed = False
            self._last_command = None
            self._trajectory = None
            self._pid = None
            self._last_ticks = None
            self._return_pose = None
            self._servo_trajectory = None

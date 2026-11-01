"""复用 LeRobot Feetech 总线实现 SO-100/101 主从臂，连接时只读且不自动校准。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

from math import isfinite
from time import monotonic, monotonic_ns

from ..contracts import Action, Observation
from ..safety import JOINTS
from .calibration import ArmCalibration
from .transport import RobotTransport


class SOArmTransport(RobotTransport):
    def __init__(self, port: str, calibration: ArmCalibration, role: str, max_velocity: float = 0.25, timeout: float = 0.25) -> None:
        if role not in ("leader", "follower") or not port:
            raise ValueError("需要明确主从角色和串口")
        if not all(isfinite(v) and v > 0 for v in (max_velocity, timeout)):
            raise ValueError("速度和通信超时必须为有限正数")
        self.port, self.calibration, self.role = port, calibration, role
        self.limits = calibration.limits
        self.max_velocity, self.timeout = max_velocity, timeout
        self._bus = None
        self._armed = False
        self._last_command: dict[str, float] | None = None
        self._last_sent = 0.0

    def connect(self) -> None:
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
        return Observation(monotonic_ns(), positions)

    def arm(self) -> None:
        if self.role != "follower":
            raise RuntimeError("主臂只读，禁止力矩使能")
        bus = self._connected()
        current = self.read_observation().joint_positions
        bus.sync_write("Goal_Position", self.calibration.ticks(current), normalize=False)
        self._armed = True  # 使能中途异常时 disconnect 也必须释放已启用的轴。
        try:
            bus.enable_torque()
            if not all(bus.sync_read("Torque_Enable", normalize=False).values()):
                raise RuntimeError("从臂力矩使能回读不完整")
            self._last_command, self._last_sent = dict(current), monotonic()
        except BaseException:
            self.disconnect()
            raise

    def send_action(self, action: Action) -> None:
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
            command = self.limits.constrain(action, current, max(dt, 0.0001), self.max_velocity)
            # 同时约束上一目标和本次反馈，避免重复读取滞后导致目标跳变。
            if self._last_command is not None:
                command = self.limits.constrain(command, self._last_command, max(dt, 0.0001), self.max_velocity)
            ticks = self.calibration.ticks(command.joint_positions)
            bus.sync_write("Goal_Position", ticks, normalize=False)
            self._last_command = self.calibration.angles(ticks)
            self._last_sent = now
        except BaseException:
            self.disconnect()
            raise

    @property
    def applied_action(self) -> Action:
        if self._last_command is None:
            raise RuntimeError("尚无已发送目标")
        return Action(dict(self._last_command))

    def disconnect(self) -> None:
        bus, self._bus = self._bus, None
        try:
            if bus is not None and bus.is_connected:
                bus.disconnect(disable_torque=self._armed)
        finally:
            self._armed = False
            self._last_command = None

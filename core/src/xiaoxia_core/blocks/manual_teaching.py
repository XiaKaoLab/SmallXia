"""只读录制单只真机的手动示教，复用匹配校准，转换为 SO100 显示坐标并生成下一姿态标签。
Created on 2026-11-02; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from dataclasses import asdict
import json
from pathlib import Path
import re
from time import monotonic, sleep, time_ns

from ..communication.display_alignment import DisplayAlignment
from ..communication.display_frame import DisplayFrame
from ..communication.official_calibration import OfficialCalibrationStore, OfficialUrdfMap
from ..safety import JOINTS, JointLimits
from .workflow import BlockWorkflow


class ManualTeaching:
    def record(self, port, seconds=10, camera='none', task='真机手动示教'):
        if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port):
            raise ValueError('请选择 COM 口')
        if type(seconds) not in (int, float) or not 1 <= seconds <= 3600:
            raise ValueError('录制时长须为 1–3600 秒')
        from lerobot.motors import Motor, MotorNormMode
        from lerobot.motors.feetech import FeetechMotorsBus

        class ReadOnlyBus(FeetechMotorsBus):
            def write(self, *args, **kwargs): raise RuntimeError('示教只读')
            def sync_write(self, *args, **kwargs): raise RuntimeError('示教只读')
            def enable_torque(self, *args, **kwargs): raise RuntimeError('示教只读')
            def disable_torque(self, *args, **kwargs): raise RuntimeError('示教只读')

        pending = []
        for path in DisplayAlignment.root.glob('*/state.json'):
            state = json.loads(path.read_text(encoding='utf-8'))
            if state.get('port') == port and state.get('status') not in ('failed', 'stopped', 'saved'):
                (path.parent / 'stop').touch()
                pending.append(path)
        deadline = monotonic() + 3
        while pending:
            pending = [path for path in pending if json.loads(path.read_text(encoding='utf-8')).get('status') not in ('failed', 'stopped', 'saved')]
            if pending and monotonic() > deadline:
                raise ValueError('请先停止真机映射')
            sleep(.05)
        bus = ReadOnlyBus(port, {name: Motor(i, 'sts3215', MotorNormMode.DEGREES) for i, name in enumerate(JOINTS, 1)})
        workflow = BlockWorkflow()
        BlockWorkflow.http(f'hardware/arms/{port}/observe-stop', {})
        try:
            bus.connect()
            bus.set_timeout(150)
            if any(bus.sync_read('Torque_Enable', normalize=False).values()):
                raise ValueError('手动示教需要先关闭力矩')
            calibration = {name: asdict(row) for name, row in bus.read_calibration().items()}
            path, _ = OfficialCalibrationStore.reuse(calibration, port)
            limits = JointLimits.from_urdf(Path(__file__).resolve().parents[4] / 'table/public/robots/so100/so100_mid_calib.urdf')
            mapping = OfficialUrdfMap(calibration, limits)
            offset = DisplayFrame.load(port, calibration)
            dataset = workflow.client.create_dataset(task, fps=2, cameras=[] if camera == 'none' else [camera],
                action_semantics='waypoint_next_target', state_source='manual_encoder', calibration_path=path, port=port)
            workflow.remember(dataset_id=dataset['id'])
            started = monotonic()
            for index in range(max(2, round(seconds * 2))):
                sleep(max(0, started + index / 2 - monotonic()))
                angles = DisplayFrame.apply(mapping.angles(bus.sync_read('Present_Position', normalize=False)), offset)
                print(json.dumps({'hardware_feedback':{'port':port,'physical':True,'source':'hardware_feedback','unit':'rad',
                    'render_joint_positions':angles,'joint_positions':angles,'read_only_following':True,
                    'feedback_age_ms':0,'observed_at_ns':time_ns()}},ensure_ascii=False),flush=True)
                limits.validate(angles)
                workflow.client.request(f"datasets/{dataset['id']}/frames", {'action': angles, 'observation': angles})
                workflow.emit('请转动各个关节', step=index + 1, total=max(2, round(seconds * 2)))
            return workflow.finish()
        finally:
            try:
                if bus.is_connected: bus.disconnect(disable_torque=False)
            finally:
                try: BlockWorkflow.http(f'hardware/arms/{port}/observe-resume', {})
                except Exception: pass

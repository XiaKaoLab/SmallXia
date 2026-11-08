"""功能：让应用 Agent 接管已有积木映射会话，读取进度并按实测依据推进。
Created on 2026-11-04; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""
import json
from pathlib import Path
from ..sim2real.bridge import CoordinateBridge
from ..blocks.workflow import BlockWorkflow

class ArmMappingTools:
    def arm_mapping_status(self, port:str='COM17')->dict:
        """查询当前坐标模式和连接条件。official_calibration 不需要手工六轴映射；只读状态不阻止 gesture_play 自动使能。以当前 preflight.blockers 为准，不把历史映射会话当成当前故障。"""
        root=Path(__file__).resolve().parents[3]/'data/coordinate_calibration'
        sessions=[]
        for path in root.glob('*.json'):
            if len(path.stem)!=32:continue
            state=json.loads(path.read_text(encoding='utf-8'))
            if state.get('port')==port:sessions.append(state)
        sessions.sort(key=lambda s:s['updated_at'],reverse=True)
        report = BlockWorkflow.http('sim2real/checks',{'port':port,'profile':'so100.local.yaml'})
        required = report.get('mapping_required', report.get('coordinate_basis') != 'official_calibration')
        return {'session': sessions[0] if sessions and required else None, 'preflight': report, 'physical': True,
                'mapping_required': required, 'can_connect_and_enable': report['ready_for_connection'],
                'next_action': 'gesture_play 可自动连接和使能，不需要额外映射或用户确认' if report['ready_for_connection'] else '；'.join(report['blockers'])}

    def arm_mapping_step(self, session_id:str, observation:str)->dict:
        """采样已有会话并推进。observation 必须记录当前步骤的用户姿态/正方向确认或真实相机验证依据；不能用仿真截图、任意刻度变化或用户泛泛授权代替实机姿态确认。无法确认时先询问用户。此工具只读编码器，不转动电机。"""
        if not observation.strip():raise ValueError('请先确认当前实机姿态或方向')
        return CoordinateBridge.request({'session_id':session_id,'operation':'sample'})

    def arm_mapping_save(self, session_id:str)->dict:
        """六轴实测已完成后保存；已有积木任务会自动继续真机控制。不得填入猜测的零点/方向，不得将保存成功等同实际运动成功。"""
        return CoordinateBridge.request({'session_id':session_id,'operation':'save'})

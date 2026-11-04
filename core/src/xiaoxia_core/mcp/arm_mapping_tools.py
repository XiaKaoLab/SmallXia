"""功能：让应用 Agent 接管已有积木映射会话，读取进度并按实测依据推进。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
import json
from pathlib import Path
from ..sim2real.bridge import CoordinateBridge
from ..blocks.workflow import BlockWorkflow

class ArmMappingTools:
    def arm_mapping_status(self, port:str='COM17')->dict:
        """查询积木映射会话及真机控制状态。zero/direction 尚未确认；不得将创建会话当作校准完成。"""
        root=Path(__file__).resolve().parents[3]/'data/coordinate_calibration'
        sessions=[]
        for path in root.glob('*.json'):
            if len(path.stem)!=32:continue
            state=json.loads(path.read_text(encoding='utf-8'))
            if state.get('port')==port:sessions.append(state)
        sessions.sort(key=lambda s:s['updated_at'],reverse=True)
        return {'session':sessions[0] if sessions else None,'preflight':BlockWorkflow.http('sim2real/checks',{'port':port,'profile':'so100.local.yaml'}),'physical':True}

    def arm_mapping_step(self, session_id:str, observation:str)->dict:
        """采样已有会话并推进。observation 必须记录当前步骤的用户姿态/正方向确认或真实相机验证依据；不能用仿真截图、任意刻度变化或用户泛泛授权代替实机姿态确认。无法确认时先询问用户。此工具只读编码器，不转动电机。"""
        if not observation.strip():raise ValueError('请先确认当前实机姿态或方向')
        return CoordinateBridge.request({'session_id':session_id,'operation':'sample'})

    def arm_mapping_save(self, session_id:str)->dict:
        """六轴实测已完成后保存；已有积木任务会自动继续真机控制。不得填入猜测的零点/方向，不得将保存成功等同实际运动成功。"""
        return CoordinateBridge.request({'session_id':session_id,'operation':'save'})

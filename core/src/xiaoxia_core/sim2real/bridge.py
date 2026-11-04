"""功能：为积木坐标向导提供受限 API 桥接，只更新仿真参考姿态。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
import json,os
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from ..imitation.api_jobs import identifier

class CoordinateBridge:
    @staticmethod
    def request(request):
        sid=identifier(request.get('session_id'));operation=request.get('operation')
        if operation not in ('state','sample','save','cancel'):raise ValueError('不支持的坐标操作')
        endpoint=sid if operation=='state' else sid+'/'+operation
        body=request.get('body',{})
        req=Request('http://127.0.0.1:8766/api/v1/sim2real/calibrations/'+endpoint,
            data=None if operation=='state' else json.dumps(body).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['XIAOXIA_MOTION_TOKEN']})
        try:
            with urlopen(req,timeout=40) as response:state=json.load(response)
        except HTTPError as error:raise ValueError(json.load(error).get('error','校准失败')) from None
        result={'state':state}
        if state['stage'] in ('zero','direction'):
            from ..mcp.server import TableModelTools
            TableModelTools().table_move_joints(**state['reference_rad'])
        if operation=='save' and state['stage']=='saved' and not state.get('resume_control'):
            from ..communication.display_alignment import DisplayAlignment
            try:result['display_alignment']=DisplayAlignment.start_mapping(state['port'])
            except Exception as error:result['follow_error']=str(error)
        return result

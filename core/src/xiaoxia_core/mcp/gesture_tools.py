"""功能：向 Agent 提供已有动作查询、顺序编排与后台运行状态，绑定器灵目标。
Created on 2026-11-08; Updated on 2026-11-08
@author: https://github.com/Linmoqian
"""
from ..gestures.library import GestureLibrary
from ..blocks.workflow import BlockWorkflow
from ..imitation.api_jobs import identifier


class GestureTools:
    def __init__(self, bound_target=None, motion_enabled=False, profile='so100.local.yaml'):
        self.bound_target, self.motion_enabled = bound_target, motion_enabled
        self.profile = profile

    def gesture_list(self) -> dict:
        """查询本地已有动作：挥手wave、旋转spin、鞠躬bow、原标签False的未命名动作。源动作相对当前姿态缩放，非原校准绝对轨迹；不运动。"""
        catalog = GestureLibrary().catalog()
        return {k: catalog[k] for k in ('source', 'revision', 'license', 'representation', 'note', 'actions')}

    def gesture_play(self, actions: list[str], target: str = 'simulation', amplitude_deg: float = 15, variant: int = 0) -> dict:
        """将动作按列表顺序编排为一个后台程序，例如[wave,bow,wave]，可重复名称。target为simulation或serial:COM17。仅在用户要求对应目标运动时调用；真机使用舵机内部轨迹逐关键姿态到位，不复现原30FPS时序。默认相对当前姿态每轴最大变化15度，variant为0起示例编号。先查询动作库；返回任务后用gesture_status确认，超时不重发。"""
        if self.bound_target is not None:
            if target != self.bound_target: raise ValueError('只能调用器灵绑定目标：'+self.bound_target)
            if target != 'simulation' and not self.motion_enabled: raise ValueError('器灵未启用真机运动')
        if target != 'simulation':
            import re
            if not re.fullmatch(r'serial:COM[1-9][0-9]*', target): raise ValueError('请选择仿真或串口目标')
        GestureLibrary().plan(actions, amplitude_deg, variant)
        source = ('from xiaoxia_core.gestures.library import GestureLibrary\n'
                  f'GestureLibrary().play({actions!r}, target={target!r}, amplitude_deg={amplitude_deg!r}, variant={variant!r}, profile={self.profile!r})\n')
        job = BlockWorkflow.http('programs/jobs', {'source': source})
        return {'program': job, 'target': target, 'physical': target != 'simulation', 'actions': actions,
                'amplitude_deg': amplitude_deg, 'source': GestureLibrary().catalog()['source']}

    def gesture_status(self, program_id: str) -> dict:
        """查询动作程序真实状态和日志。succeeded表示程序完成，不代表真实任务成功或画面已验证。"""
        return BlockWorkflow.http('programs/jobs/'+identifier(program_id))

    def gesture_stop(self, program_id: str) -> dict:
        """停止动作编排；真机沿现有流程回到运行起始姿态并失能。返回停止请求，随后查状态确认完成。"""
        return BlockWorkflow.http('programs/jobs/'+identifier(program_id)+'/stop', {})

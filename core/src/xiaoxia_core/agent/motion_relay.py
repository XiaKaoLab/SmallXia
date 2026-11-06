"""功能：让器灵根据已有动作规划短接龙，仅返回受约束的动作数据，不执行运动。
Created on 2026-11-06; Updated on 2026-11-06
@author: https://github.com/Linmoqian
"""
import json
from dataclasses import replace
from math import isfinite
from ..llm import LLMConfig, OpenAILLM


class MotionRelayPlanner:
    joints = ('shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper')

    def plan(self, request):
        poses = request.get('poses')
        if not isinstance(poses, list) or not 1 <= len(poses) <= 8:
            raise ValueError('请先编一段机械臂动作')
        for pose in poses:
            if not isinstance(pose, dict) or set(pose) != set(self.joints) or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in pose.values()
            ): raise ValueError('动作姿态无效')
        waits = request.get('waits', [0] * len(poses))
        if not isinstance(waits, list) or len(waits) != len(poses) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) or not 0 <= v <= 3600 for v in waits
        ): raise ValueError('动作停顿无效')
        history = request.get('previous_ideas', [])
        if not isinstance(history, list) or any(not isinstance(v, str) for v in history): raise ValueError('接龙历史无效')
        config = LLMConfig.from_env()
        model = request.get('model', 'default')
        if model != 'default':
            if not isinstance(model, str) or not model.strip() or len(model) > 200: raise ValueError('模型名称无效')
            config = replace(config, model=model)
        with OpenAILLM(replace(config, max_output_tokens=1200, max_retries=0)) as llm:
            response = llm.generate(json.dumps({'poses_rad': poses, 'wait_after_each_pose_seconds': waits, 'previous_ideas': [v[:200] for v in history[-5:]]}, ensure_ascii=False), instructions=(
                '你是器灵，正在与用户轮流编机械臂动作。根据已有姿态的节奏和方向，续写一小段有呼应但不机械重复的动作。'
                '只输出 JSON，不输出代码或 Markdown。格式 {"text":"一句自然中文说明你接的动作，不声称已经运行",'
                '"steps":[{"offsets_deg":{"wrist_roll":5},"seconds":1.5}]}。'
                '生成2到4步，offsets_deg 是相对最后一个用户姿态的偏移，单位度，关节名仅限'
                + ','.join(self.joints) + '。每个偏移绝对值不超过12度，seconds 为0.5到3秒。'
                '尽量一次只改变1到2轴，保留用户动作特点。系统会另加一步返回用户最后姿态。'
                '不要照抄 previous_ideas 中的动作。'
            ))
        raw = response.text.strip()
        if raw.startswith('```'): raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
        plan = json.loads(raw)
        steps = plan.get('steps')
        if not isinstance(steps, list) or not 2 <= len(steps) <= 4: raise ValueError('器灵没有返回完整动作，请再接一次')
        for step in steps:
            offsets, seconds = step.get('offsets_deg'), step.get('seconds')
            if not isinstance(offsets, dict) or not offsets or any(n not in self.joints for n in offsets): raise ValueError('接龙关节无效')
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) or abs(v) > 12 for v in offsets.values()): raise ValueError('接龙偏移无效')
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not isfinite(seconds) or not .5 <= seconds <= 3: raise ValueError('接龙停顿无效')
        text = plan.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 160: raise ValueError('接龙说明无效')
        return {'steps': steps, 'text': text, 'model': response.model}

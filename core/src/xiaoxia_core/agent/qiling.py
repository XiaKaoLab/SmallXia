"""器灵独立 Agent：模型选择、按积木隔离会话，仅开放机械臂 MCP。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import json
import os
import sys
from dataclasses import asdict,replace
from pathlib import Path
from contextlib import closing
from ..llm import LLMConfig,OpenAILLM
from .sessions import SessionStore
from .skills import SkillRegistry
from .runtime import SimpleAgent
from ..mcp.qiling_profile import QiLingProfile


class QiLingModels:
    @staticmethod
    def list():
        config=LLMConfig.from_env()
        models=list(dict.fromkeys([config.model,*[x.strip() for x in os.environ.get('OPENAI_MODELS','').split(',') if x.strip()]]))
        available=True
        try:
            from openai import OpenAI
            with OpenAI(base_url=config.base_url,timeout=8,max_retries=0) as client:
                models=list(dict.fromkeys([*models,*(item.id for item in client.models.list())]))
        except Exception:available=False
        return {'models':models,'default_model':config.model,'provider_list_available':available,
            'tools':sorted(QiLingProfile.tools),'configured':bool(os.environ.get('OPENAI_API_KEY'))}


class QiLingAgent:
    def __init__(self):
        self.root=Path(__file__).resolve().parents[3]
        self.skills=SkillRegistry(self.root/'skills')

    def session(self,node_id):
        if not isinstance(node_id,str) or not node_id or len(node_id)>128:raise ValueError('器灵积木 ID 无效')
        import hashlib
        identity=hashlib.sha256(node_id.encode('utf-8')).hexdigest()[:32]
        self.store=SessionStore(self.root/f'data/qiling/{identity}.sqlite3')
        sessions=self.store.list_sessions()
        return sessions[0] if sessions else self.store.create()

    def run(self,node_id,message,model='default',target='simulation',profile='so100.local.yaml',enable_motion=False):
        if not isinstance(message,str) or not message.strip() or len(message)>8000:raise ValueError('器灵消息需要1–8000字')
        config=LLMConfig.from_env()
        if model!='default':
            if not isinstance(model,str) or not model.strip() or len(model)>200:raise ValueError('模型名称无效')
            config=replace(config,model=model.strip())
        session=self.session(node_id)
        context={'target':target,'profile':profile,'enable_motion':enable_motion is True}
        with OpenAILLM(config,enable_mcp=True,mcp_profile='qiling',mcp_context=context) as llm:
            agent=SimpleAgent(llm,self.store,self.skills,instructions=QiLingProfile.instructions_for(context),persona='')
            with closing(agent.stream(session,message)) as events:
                for event in events:
                    value=asdict(event);value['node_id']=node_id
                    print(json.dumps({'qiling':value},ensure_ascii=False),flush=True)


def main():
    sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
    request=json.loads(sys.stdin.readline())
    try:QiLingAgent().run(request['node_id'],request['message'],request.get('model','default'),request.get('target','simulation'),request.get('profile','so100.local.yaml'),request.get('enable_motion',False))
    except Exception:
        print(json.dumps({'qiling':{'type':'error','node_id':request.get('node_id'),'text':'器灵本轮未完成，请检查模型配置或服务状态。'}},ensure_ascii=False),flush=True)
        raise


if __name__=='__main__':main()

"""积木内运行器灵子进程，转发回复并在程序停止时清理 Agent/MCP 进程。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import json,os,subprocess,sys
from pathlib import Path
from threading import Thread,Event,Lock
from queue import Queue,Empty


class QiLingBlock:
    _bindings = {}
    _emit_lock=Lock()

    @classmethod
    def emit(cls,value):
        with cls._emit_lock:print(json.dumps(value,ensure_ascii=False),flush=True)

    @classmethod
    def load(cls,node_id,name='器灵',target='simulation',model='default',profile='so100.local.yaml',enable_motion=False):
        if not isinstance(name,str) or not name.strip() or len(name)>32:raise ValueError('器灵名称需要1–32字')
        if not isinstance(model,str) or not model.strip():raise ValueError('请选择器灵模型')
        name=name.strip()
        old=cls._bindings.get(name,{})
        if old.get('lease'):old['lease'].close()
        lease=None;load_text=None
        if target!='simulation':
            import re
            if not isinstance(target,str) or not re.fullmatch(r'serial:COM[1-9][0-9]*',target):raise ValueError('请选择机械臂目标')
            from .workflow import BlockWorkflow
            port=target[7:]
            report=BlockWorkflow.http('sim2real/checks',{'port':port,'profile':profile})
            load_text='已载入，只读。' if report['ready_for_connection'] else '坐标待确认，当前只读。'
            cls.emit({'qiling':{'type':'preflight','node_id':node_id,'spirit':name,'target':target,
                'text':'坐标预检通过' if report['ready_for_connection'] else '；'.join(report['blockers']),
                'ready':report['ready_for_connection'],'physical':True}})
            if enable_motion is True:
                if not report['ready_for_connection']:raise ValueError('；'.join(report['blockers']))
                from ..communication.hardware_client import HardwareClient
                HardwareClient(port).connect(profile,enable_motion=True)
                from ..sim2real.lease import HardwareLease
                lease=HardwareLease(port,node_id,name,cls.emit);lease.start()
        cls._bindings[name]={'agent_id':node_id,'spirit':name,'target':target,'model':model,
            'profile':profile,'enable_motion':enable_motion is True,'lease':lease}
        cls.emit({'qiling':{'type':'loaded','node_id':node_id,'spirit':name,'target':target,'model':model,
            'enable_motion':enable_motion is True,'text':load_text}})

    @classmethod
    def check(cls,target,profile='so100.local.yaml',node_id='sim2real-check'):
        import re
        if not isinstance(target,str) or not re.fullmatch(r'serial:COM[1-9][0-9]*',target):raise ValueError('请选择真机串口')
        from .workflow import BlockWorkflow
        report=BlockWorkflow.http('sim2real/checks',{'port':target[7:],'profile':profile})
        cls.emit({'qiling':{'type':'preflight','node_id':node_id,'spirit':'Sim2Real','target':target,
            'ready':report['ready_for_connection'],'text':'坐标预检通过' if report['ready_for_connection'] else '；'.join(report['blockers'])}})
        return report

    def send(self,node_id,name,message):
        name=name.strip() if isinstance(name,str) else ''
        binding=self._bindings.get(name)
        if binding is None:raise ValueError('请先向机械臂载入对应器灵，再发送消息')
        return self.run(node_id,message,binding['model'],agent_id=binding['agent_id'],spirit=name,target=binding['target'],profile=binding.get('profile','so100.local.yaml'),enable_motion=binding.get('enable_motion',False))

    def run(self,node_id,message,model='default',*,agent_id=None,spirit='器灵',target='simulation',profile='so100.local.yaml',enable_motion=False):
        options={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
        process=subprocess.Popen([sys.executable,'-u','-m','xiaoxia_core.agent.qiling'],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=sys.stderr,text=True,encoding='utf-8',**options)
        lines=Queue();drained=Event()
        def stdout():
            try:
                for line in process.stdout:lines.put(line)
            finally:drained.set()
        Thread(target=stdout,daemon=True).start()
        completed=False;reply=''
        try:
            process.stdin.write(json.dumps({'node_id':agent_id or node_id,'message':message,'model':model,'target':target,'profile':profile,'enable_motion':enable_motion is True},ensure_ascii=False)+'\n');process.stdin.close()
            while process.poll() is None or not drained.is_set() or not lines.empty():
                directory=os.environ.get('XIAOXIA_PROGRAM_DIR')
                if directory and (Path(directory)/'stop').exists():raise InterruptedError('器灵已停止')
                try:line=lines.get(timeout=.05)
                except Empty:continue
                try:
                    value=json.loads(line)
                    event=value.get('qiling',{})
                    if event:
                        event.update(node_id=node_id,agent_id=agent_id or node_id,spirit=spirit,target=target)
                        self.emit({'qiling':event})
                    else:print(line.rstrip(),flush=True)
                    if event.get('type')=='completed':
                        completed=True;reply=event['result']['text']
                except (ValueError,KeyError,TypeError):pass
            if process.returncode or not completed:raise RuntimeError('器灵回答未完成，请检查模型或连接')
            return reply
        finally:
            if process.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    import signal
                    os.killpg(process.pid,signal.SIGTERM)
                process.wait(timeout=5)

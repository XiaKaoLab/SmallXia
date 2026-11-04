/** 功能：统一订阅真机反馈驱动模型，覆盖积木、Agent、API与回位全过程。
 * Created on 2026-11-03; Updated on 2026-11-04
 * @author: https://github.com/Linmoqian
 */
import { JOINTS } from "./blocks/positionBlock";
import { agentClient } from "./chat/AgentClient";
interface Feedback {physical?:boolean;source?:string;unit?:string;port?:string;target?:string|Record<string,number>;status?:string;feedback_age_ms?:number;observed_at_ns?:number;joint_positions?:Record<string,number>;render_joint_positions?:Record<string,number>;release?:{start_reached?:boolean}}
export class HardwareControlPreview {
  private pose:Record<string,number>|null=null;
  private smoothed:Record<string,number>|null=null;
  private target="";private received=0;private rendered=0;private streamAt=0;
  private phase="";private disposed=false;private requestId="";
  private retry?:ReturnType<typeof setTimeout>;
  private readonly label=document.createElement("div");
  private readonly receive=(raw:Event)=>{
    if(performance.now()-this.streamAt<500)return;
    this.accept((raw as CustomEvent<Feedback>).detail);
  };
  private readonly clear=()=>{this.pose=null;this.smoothed=null;this.target="";this.label.hidden=true;};
  private readonly ended=()=>{ /* 控制任务结束后仍订阅回起点反馈，保留最后实测姿态。 */ };
  constructor(host:HTMLElement){
    this.label.className="hardware-control-preview-label";this.label.hidden=true;host.append(this.label);
    window.addEventListener("table:hardware-control-feedback",this.receive);
    window.addEventListener("table:hardware-control-ended",this.ended);
    window.addEventListener("table:hardware-preview-clear",this.clear);
    if(agentClient.desktop)void this.stream();
  }
  private accept(event:Feedback):void{
    const target=typeof event.target==="string"?event.target:(event.port?`serial:${event.port}`:"");
    if(target===this.target&&["stopped","failed"].includes(event.status??"")){this.phase="已停止";this.label.dataset.phase=this.phase;}
    const positions=event.render_joint_positions??event.joint_positions;
    if(event.physical!==true||event.unit!=="rad"||!/^serial:COM[1-9][0-9]*$/.test(target)||!positions||event.feedback_age_ms==null||event.feedback_age_ms>500)return;
    if(!JOINTS.every(([name])=>Number.isFinite(positions[name])))return;
    if(this.target!==target||!this.smoothed)this.smoothed={...positions};
    this.pose={...positions};this.target=target;this.received=performance.now();this.label.hidden=false;
    this.phase=event.status==="returning_zero"?"返回起始位置":event.status==="stopped"?"已停止":event.status==="failed"?"已停止":"实测同步";
    this.label.dataset.target=target;this.label.dataset.phase=this.phase;
    this.label.dataset.observedAt=String(event.observed_at_ns??0);
  }
  private async stream():Promise<void>{
    this.requestId=crypto.randomUUID();
    try{
      await agentClient.hardwarePreview<{sessions:Feedback[]}>(this.requestId,state=>{
        if(this.disposed)return;
        const active=state.sessions.filter(s=>["ready","moving","returning_zero"].includes(s.status??""));
        const selected=active.find(s=>`serial:${s.port}`===this.target)??active[0]??state.sessions.find(s=>`serial:${s.port}`===this.target);
        if(selected){this.streamAt=performance.now();this.accept(selected);}
      });
    }catch{ /* 服务重启后重新订阅；从不重发电机动作。 */ }
    if(!this.disposed)this.retry=setTimeout(()=>void this.stream(),1000);
  }
  get positions():Record<string,number>|null {
    if(!this.pose||!this.smoothed)return null;
    const now=performance.now(),dt=this.rendered?Math.min((now-this.rendered)/1000,.1):.016;this.rendered=now;
    const alpha=1-Math.exp(-dt/.04);
    for(const [name] of JOINTS)this.smoothed[name]+=(this.pose[name]-this.smoothed[name])*alpha;
    const waiting=now-this.received>1000&&!["已停止"].includes(this.phase);
    const text=`真机 ${this.target.slice(7)} · ${waiting?"等待反馈":this.phase}`;
    if(this.label.textContent!==text)this.label.textContent=text;
    return this.smoothed;
  }
  dispose():void {
    this.disposed=true;clearTimeout(this.retry);if(this.requestId)void agentClient.cancel(this.requestId).catch(()=>undefined);
    window.removeEventListener("table:hardware-control-feedback",this.receive);window.removeEventListener("table:hardware-control-ended",this.ended);window.removeEventListener("table:hardware-preview-clear",this.clear);this.label.remove();
  }
}

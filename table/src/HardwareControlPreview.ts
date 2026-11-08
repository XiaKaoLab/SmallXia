/** 功能：统一订阅真机反馈驱动模型，覆盖积木、Agent、API与回位全过程。
 * Created on 2026-11-03; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
import "./robot-view-switch.css";
import { JOINTS } from "./blocks/positionBlock";
import { agentClient } from "./chat/AgentClient";
interface Feedback {physical?:boolean;source?:string;unit?:string;port?:string;target?:string|Record<string,number>;status?:string;feedback_age_ms?:number;observed_at_ns?:number;joint_positions?:Record<string,number>;render_joint_positions?:Record<string,number>;read_only_following?:boolean;observation_error?:string;release?:{start_reached?:boolean}}
export class HardwareControlPreview {
  private pose:Record<string,number>|null=null;
  private smoothed:Record<string,number>|null=null;
  private target="";private received=0;private rendered=0;private streamAt=0;
  private phase="";private disposed=false;private requestId="";
  private following=false;
  private hardware=false; private generation=0;
  private readonly controls=document.createElement("div");
  private readonly modeButton=document.createElement("button");
  get isHardware():boolean { return this.hardware; }
  private setMode(hardware:boolean):void {
    this.hardware=hardware;this.generation++;clearTimeout(this.retry);
    if(this.requestId)void agentClient.cancel(this.requestId).catch(()=>undefined);
    this.requestId="";this.pose=null;this.smoothed=null;this.received=0;this.rendered=0;this.streamAt=0;this.following=false;
    try{localStorage.setItem("xiaoxia.robot-view-mode",hardware?"hardware":"simulation");}catch{ /* 临时窗口仍可切换。 */ }
    this.modeButton.textContent=hardware?"真机 · 只读":"仿真";
    this.modeButton.setAttribute("aria-pressed",String(hardware));
    this.modeButton.title=hardware?"切换到仿真视图":"切换到真机只读视图";
    this.label.hidden=!hardware;this.label.textContent=hardware?"等待反馈":"";
    delete this.label.dataset.observedAt;delete this.label.dataset.phase;
    this.changed(hardware);
    if(hardware&&agentClient.desktop)void this.stream(this.generation);
  }
  private retry?:ReturnType<typeof setTimeout>;
  private readonly label=document.createElement("div");
  private readonly receive=(raw:Event)=>{
    if(performance.now()-this.streamAt<500)return;
    this.accept((raw as CustomEvent<Feedback>).detail);
  };
  private readonly clear=()=>{if(this.hardware||this.following)return;this.pose=null;this.smoothed=null;this.target="";this.label.hidden=true;};
  private readonly ended=()=>{ /* 控制任务结束后仍订阅回起点反馈，保留最后实测姿态。 */ };
  constructor(host:HTMLElement,private readonly changed:(hardware:boolean)=>void=()=>undefined){
    this.controls.className="robot-view-switch";
    this.modeButton.type="button";this.modeButton.className="robot-view-mode";
    this.modeButton.setAttribute("aria-label","切换仿真与真机只读视图");
    this.modeButton.onclick=()=>this.setMode(!this.hardware);
    this.label.className="hardware-control-preview-label";this.label.setAttribute("role","status");this.label.setAttribute("aria-live","polite");
    this.controls.append(this.modeButton,this.label);host.append(this.controls);
    window.addEventListener("table:hardware-control-feedback",this.receive);
    window.addEventListener("table:hardware-control-ended",this.ended);
    window.addEventListener("table:hardware-preview-clear",this.clear);
    let hardware=false;
    try{hardware=localStorage.getItem("xiaoxia.robot-view-mode")==="hardware";}catch{ /* 默认仿真。 */ }
    this.setMode(hardware);
  }
  private accept(event:Feedback):boolean{
    if(!this.hardware||this.disposed)return false;
    const target=typeof event.target==="string"?event.target:(event.port?`serial:${event.port}`:"");
    if(target===this.target)this.following=event.read_only_following===true||["ready","moving","returning_zero"].includes(event.status??"");
    if(target===this.target&&["stopped","failed"].includes(event.status??"")){this.phase=event.observation_error?"等待反馈":"已停止";this.label.dataset.phase=this.phase;}
    const positions=event.render_joint_positions;
    if(event.physical!==true||event.unit!=="rad"||!/^serial:COM[1-9][0-9]*$/.test(target)||!positions||event.feedback_age_ms==null||event.feedback_age_ms>500)return false;
    if(!JOINTS.every(([name])=>Number.isFinite(positions[name])))return false;
    if(this.target!==target||!this.smoothed)this.smoothed={...positions};
    this.pose={...positions};this.target=target;this.received=performance.now();this.label.hidden=false;
    this.following=event.read_only_following===true||["ready","moving","returning_zero"].includes(event.status??"");
    this.phase=event.read_only_following?"只读同步":event.observation_error?"等待反馈":event.status==="returning_zero"?"返回起始位置":event.status==="stopped"?"已停止":event.status==="failed"?"已停止":"实测同步";
    this.label.dataset.target=target;this.label.dataset.phase=this.phase;
    this.label.dataset.observedAt=String(event.observed_at_ns??0);
    return true;
  }
  private async stream(generation:number):Promise<void>{
    if(this.disposed||!this.hardware||generation!==this.generation)return;
    const requestId=crypto.randomUUID();this.requestId=requestId;
    try{
      await agentClient.hardwarePreview<{sessions:Feedback[]}>(requestId,state=>{
        if(this.disposed||generation!==this.generation||!this.hardware)return;
        const active=state.sessions.filter(s=>s.read_only_following||["ready","moving","returning_zero"].includes(s.status??""));
        const selected=active.find(s=>`serial:${s.port}`===this.target)??active[0]??state.sessions.find(s=>`serial:${s.port}`===this.target)??state.sessions[state.sessions.length - 1];
        if(selected&&this.accept(selected))this.streamAt=performance.now();
      });
    }catch{ /* 服务重启后重新订阅；从不重发电机动作。 */ }
    if(!this.disposed&&this.hardware&&generation===this.generation)this.retry=setTimeout(()=>void this.stream(generation),1000);
  }
  get positions():Record<string,number>|null {
    if(!this.hardware||!this.pose||!this.smoothed)return null;
    const now=performance.now(),dt=this.rendered?Math.min((now-this.rendered)/1000,.1):.016;this.rendered=now;
    const alpha=1-Math.exp(-dt/.04);
    for(const [name] of JOINTS)this.smoothed[name]+=(this.pose[name]-this.smoothed[name])*alpha;
    const waiting=now-this.received>1000&&!["已停止"].includes(this.phase);
    const text=`真机 ${this.target.slice(7)} · ${waiting?"等待反馈":this.phase}`;
    if(this.label.textContent!==text)this.label.textContent=text;
    return this.smoothed;
  }
  dispose():void {
    this.disposed=true;this.generation++;clearTimeout(this.retry);if(this.requestId)void agentClient.cancel(this.requestId).catch(()=>undefined);
    window.removeEventListener("table:hardware-control-feedback",this.receive);window.removeEventListener("table:hardware-control-ended",this.ended);window.removeEventListener("table:hardware-preview-clear",this.clear);this.controls.remove();
  }
}

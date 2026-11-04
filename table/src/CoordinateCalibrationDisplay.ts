/** 功能：承接积木映射标定回执，展示参考姿态并完成采样、保存和只读跟随。
 * Created on 2026-11-04; Updated on 2026-11-04
 * @author: https://github.com/Linmoqian
 */
import { agentClient } from "./chat/AgentClient";
interface CoordinateState {id:string;port:string;stage:string;instruction:string;joint?:string;reference_rad:Record<string,number>;close_panel?:boolean}
export class CoordinateCalibrationDisplay {
  private state?:CoordinateState;
  private busy=false;
  private generation=0;
  private readonly panel=document.createElement("section");
  private readonly text=document.createElement("span");
  private readonly next=document.createElement("button");
  private readonly close=document.createElement("button");
  private readonly notice=document.createElement("div");
  private timer?:ReturnType<typeof setTimeout>;
  private readonly start=(event:Event)=>{void this.open((event as CustomEvent<CoordinateState>).detail);};
  constructor(host:HTMLElement){
    this.panel.className="coordinate-calibration-panel";this.panel.hidden=true;
    this.panel.setAttribute("aria-label","关节映射校准");this.text.setAttribute("aria-live","polite");
    this.close.textContent="取消";this.close.onclick=()=>void this.act("cancel");
    this.next.onclick=()=>void this.act(this.state?.stage==="review"?"save":"sample");
    this.panel.append(this.text,this.next,this.close);this.notice.className="calibration-saved-notice";this.notice.hidden=true;
    this.notice.setAttribute("role","status");host.append(this.panel,this.notice);
    window.addEventListener("table:coordinate-calibration",this.start);
  }
  private async open(state:CoordinateState):Promise<void>{
    if(this.state&&this.state.id!==state.id){this.notice.textContent="请先完成或取消当前校准";this.notice.hidden=false;return;}
    this.state=state;this.panel.hidden=false;this.notice.hidden=true;this.render();
    await this.act("state");
  }
  private render():void{
    const s=this.state;if(!s)return;
    const names:Record<string,string>={shoulder_pan:"M1 肩部旋转",shoulder_lift:"M2 肩部抬升",elbow_flex:"M3 肘部弯曲",wrist_flex:"M4 腕部弯曲",wrist_roll:"M5 腕部旋转",gripper:"M6 夹爪"};
    this.text.textContent=`${s.port} · ${s.joint?names[s.joint]+" · ":""}${s.instruction}`;
    this.next.textContent=this.busy?"读取中…":s.stage==="zero"?"已对齐":s.stage==="review"?"保存":"已转动";
    this.next.disabled=this.busy;this.close.disabled=this.busy;
  }
  private async act(operation:string):Promise<void>{
    if(this.busy||!this.state)return;
    this.busy=true;this.render();const generation=this.generation;
    try{
      const result=await agentClient.request<{state:CoordinateState;display_alignment?:{id:string;port:string;mode:string}}>({action:"coordinate_request",operation,session_id:this.state.id,
        body:operation==="sample"?{pose_confirmed:this.state.stage==="zero",positive_direction_confirmed:this.state.stage==="direction"}:operation==="save"?{confirmed:true}:{}});
      if(generation!==this.generation)return;
      this.state=result.state;
      if(["saved","cancelled"].includes(result.state.stage)){
        this.panel.hidden=true;this.state=undefined;
        if(result.state.stage==="saved"){
          this.notice.textContent="已保存";this.notice.hidden=false;clearTimeout(this.timer);this.timer=setTimeout(()=>{this.notice.hidden=true;},3500);
          if(result.display_alignment)window.dispatchEvent(new CustomEvent("table:alignment-start",{detail:result.display_alignment}));
        }
      }
    }catch(error){if(generation===this.generation)this.text.textContent=String(error).replace(/^Error: /,"");}
    finally{this.busy=false;if(this.state){const message=this.text.textContent;this.render();if(message&&!message.startsWith(this.state.port))this.text.textContent=message;}}
  }
  dispose():void{this.generation++;clearTimeout(this.timer);window.removeEventListener("table:coordinate-calibration",this.start);this.panel.remove();this.notice.remove();}
}

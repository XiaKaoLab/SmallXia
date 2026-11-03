/** 功能：以真机控制反馈驱动数字孪生，不再单独打开串口，明确标注反馈新鲜度。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { JOINTS } from "./blocks/positionBlock";
import type { QiLingReceipt } from "./blocks/QiLingBlocks";
export class HardwareControlPreview {
  private pose:Record<string,number>|null=null;
  private target="";private received=0;
  private readonly label=document.createElement("div");
  private readonly receive=(raw:Event)=>{
    const event=(raw as CustomEvent<QiLingReceipt>).detail;
    if(event.physical!==true||event.source!=="hardware_feedback"||event.unit!=="rad"||!/^serial:COM[1-9][0-9]*$/.test(event.target??"")||!event.joint_positions||event.feedback_age_ms==null||event.feedback_age_ms>500)return;
    if(!JOINTS.every(([name])=>Number.isFinite(event.joint_positions![name])))return;
    this.pose={...event.joint_positions};this.target=event.target!;this.received=performance.now();this.label.hidden=false;
  };
  private readonly ended=(raw:Event)=>{
    if((raw as CustomEvent<{target:string}>).detail.target!==this.target)return;
    this.pose=null;this.label.hidden=true;this.target="";
  };
  constructor(host:HTMLElement){
    this.label.className="hardware-control-preview-label";this.label.hidden=true;host.append(this.label);
    window.addEventListener("table:hardware-control-feedback",this.receive);
    window.addEventListener("table:hardware-control-ended",this.ended);
  }
  get positions():Record<string,number>|null {
    if(!this.pose)return null;
    const fresh=performance.now()-this.received<=1000;
    const text=`真机 ${this.target.slice(7)} · ${fresh?"实测跟随":"等待反馈"}`;
    if(this.label.textContent!==text)this.label.textContent=text;
    return fresh?this.pose:null;
  }
  dispose():void {window.removeEventListener("table:hardware-control-feedback",this.receive);window.removeEventListener("table:hardware-control-ended",this.ended);this.label.remove();}
}

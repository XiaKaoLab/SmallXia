/** 功能：将器灵的真实流式回复投影到机械臂旁，显示思考、回复与结束状态气泡。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import type { QiLingReceipt } from "./blocks/QiLingBlocks";
import { ToolPresentation } from "./chat/ToolPresentation";
import "./qiling-speech.css";

export class QiLingSpeechBubble {
  private readonly panel=document.createElement("section");
  private readonly name=document.createElement("span");
  private readonly content=document.createElement("div");
  private readonly point=new THREE.Vector3();
  private timer?: ReturnType<typeof setTimeout>;
  private text="";
  private node="";
  private readonly receive=(raw:Event)=>{
    const event=(raw as CustomEvent<QiLingReceipt>).detail;
    if(!event)return;
    if(["loaded","started","preflight"].includes(event.type)) {this.node=event.node_id;this.text="";}
    else if(this.node && event.node_id!==this.node)return;
    if(!["preflight","loaded","started","delta","tool_started","tool_completed","completed","error","stopped"].includes(event.type))return;
    clearTimeout(this.timer);this.timer=undefined;
    this.name.textContent=(event.spirit??"器灵")+(event.target?.startsWith("serial:")?` · ${event.target.slice(7)}`:"");
    this.panel.hidden=false;
    this.panel.classList.toggle("is-thinking",["started","tool_started","tool_completed"].includes(event.type)&&!this.text);
    this.panel.setAttribute("aria-busy",String(!["preflight","loaded","completed","error","stopped"].includes(event.type)));
    if(event.type==="loaded"){this.content.textContent=event.text||"我来了。";this.dismissAfter(event.text?8000:3000);}
    if(event.type==="preflight"){this.content.textContent=event.text??"预检完成";this.dismissAfter(15000);}
    if(event.type==="started")this.content.textContent="…";
    if(event.type==="delta"){this.text+=event.delta??"";this.content.textContent=this.text;this.panel.classList.remove("is-thinking");}
    if(event.type==="tool_started"&&!this.text)this.content.textContent=ToolPresentation.describe(event.name??"")[0];
    if(event.type==="completed"){
      this.text=event.result?.text??this.text;this.content.textContent=this.text;
      this.dismissAfter(Math.min(45000,Math.max(12000,this.text.length*100)));
    }
    if(event.type==="error"){this.content.textContent=event.text??"这次没完成。";this.dismissAfter(12000);}
    if(event.type==="stopped"){this.content.textContent="已停止。";this.dismissAfter(3000);}
    this.content.scrollTop=this.content.scrollHeight;
  };
  constructor(private readonly host:HTMLElement) {
    this.panel.className="qiling-speech-bubble";this.panel.hidden=true;
    this.panel.setAttribute("role","status");this.panel.setAttribute("aria-live","polite");this.panel.setAttribute("aria-label","器灵气泡");
    const header=document.createElement("header");
    const close=document.createElement("button");close.type="button";close.textContent="×";close.setAttribute("aria-label","关闭器灵气泡");
    close.addEventListener("click",()=>{this.panel.hidden=true;clearTimeout(this.timer);});
    header.append(this.name,close);this.content.className="qiling-speech-content";
    this.panel.append(header,this.content);host.append(this.panel);
    window.addEventListener("table:qiling-speech",this.receive);
  }
  private dismissAfter(ms:number):void {this.timer=setTimeout(()=>{this.panel.hidden=true;},ms);}
  update(anchor:THREE.Object3D|undefined,camera:THREE.Camera):void {
    if(this.panel.hidden||!anchor)return;
    anchor.getWorldPosition(this.point);this.point.z+=.055;this.point.project(camera);
    const visible=this.point.z>=-1&&this.point.z<=1;this.panel.style.visibility=visible?"visible":"hidden";
    if(!visible)return;
    const width=this.host.clientWidth,height=this.host.clientHeight;
    const margin=Math.min(160,width/2);
    const x=Math.max(margin,Math.min(width-margin,(this.point.x*.5+.5)*width));
    const y=Math.max(Math.min(250,height*.65),Math.min(height-26,(-this.point.y*.5+.5)*height-12));
    this.panel.style.left=`${x}px`;this.panel.style.top=`${y}px`;
  }
  dispose():void {clearTimeout(this.timer);window.removeEventListener("table:qiling-speech",this.receive);this.panel.remove();}
}

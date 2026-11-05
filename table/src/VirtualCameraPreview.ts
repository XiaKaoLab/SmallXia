/** 功能：仅在显式显示时创建虚拟相机实时画面，隐藏时释放渲染资源。
 * Created on 2026-11-02; Updated on 2026-11-05
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import { agentClient } from "./chat/AgentClient";

interface TrackingFrame {status:string;physical:boolean;image?:string;found:boolean;box?:number[];width?:number;height?:number}
interface RealFrame {status:string;image?:string;source?:string;name?:string;message?:string;timestamp_ns?:number;cameras:{id:string;name:string}[]}

export class VirtualCameraPreview {
  private uploading = false;
  private lastUpload = 0;
  private inputMode = false;
  private inputImage?: HTMLImageElement;
  private inputSource = "";
  private renderer: THREE.WebGLRenderer | undefined;
  private panel: HTMLElement | undefined;
  private configuredVisible=false;
  private trackingId="";
  private tracking=false;
  private realEnabled=agentClient.desktop;
  private realRequest="";
  private realSource=localStorage.getItem("xiaoxia.real-camera")||"auto";
  private selector?:HTMLSelectElement;
  private cameraOptionsKey="";
  private overlay?: SVGSVGElement;
  private readonly trackingStart=(event:Event)=>{void this.follow((event as CustomEvent<{id:string}>).detail.id);};
  private readonly trackingStop=()=>this.stopTracking();

  constructor(private readonly host: HTMLElement) {
    window.addEventListener("table:red-tracking-start",this.trackingStart);
    window.addEventListener("table:red-tracking-stop",this.trackingStop);
    if(this.realEnabled){this.show();void this.startRealFeed();}
  }

  setVisible(visible: boolean): void {
    this.configuredVisible=visible;
    if (!visible&&!this.tracking&&!this.realEnabled) { this.release(); return; }
    this.show();
  }

  private show():void {
    if (this.renderer) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(1);
    renderer.setSize(960, 720);
    renderer.domElement.setAttribute("aria-label", "虚拟腕部相机实时画面");
    const panel = document.createElement("section");
    panel.className = "virtual-camera-preview";
    const title = document.createElement("div");
    title.className = "virtual-camera-preview-title";
    title.textContent = this.realEnabled?"真实相机 · 等待连接":"腕部相机 · 虚拟画面";
    const resize = document.createElement("button");
    resize.type="button";resize.className="virtual-camera-preview-resize";resize.textContent="展开";
    resize.setAttribute("aria-expanded","false");
    resize.addEventListener("click",()=>{
      const expanded=panel.classList.toggle("is-expanded");resize.textContent=expanded?"收起":"展开";
      resize.setAttribute("aria-expanded",String(expanded));
    });
    panel.append(title, resize, renderer.domElement);
    if(this.realEnabled){
      this.selector=document.createElement("select");this.selector.setAttribute("aria-label","真实相机设备");
      this.selector.style.cssText="display:block;width:calc(100% - 20px);margin:0 10px 8px;padding:5px;border:1px solid #b8d0c8;border-radius:6px;background:transparent;color:inherit;font-size:11px";
      this.selector.append(new Option("自动选择真实相机","auto"));
      this.selector.onchange=()=>{this.realSource=this.selector!.value;localStorage.setItem("xiaoxia.real-camera",this.realSource);if(!this.tracking)void this.startRealFeed();};
      panel.insertBefore(this.selector,renderer.domElement);
    }
    this.host.appendChild(panel);
    this.renderer = renderer;
    this.panel = panel;
  }

  setInputFrame(source: string | null, active: boolean, label = "腕部相机 · 推理输入", identity = "policy_input"): void {
    if(this.tracking&&identity!=="red_tracking")return;
    if(this.realEnabled&&identity!=="real_camera"&&identity!=="red_tracking")return;
    this.inputMode = active;
    if (!this.panel || !this.renderer) return;
    this.renderer.domElement.hidden = active;
    if (active && !this.inputImage) {
      this.inputImage = document.createElement("img");
      this.inputImage.alt = label;
      this.inputImage.width = 320; this.inputImage.height = 240;
      this.inputImage.style.objectFit = "contain";
      this.panel.appendChild(this.inputImage);
    }
    if (this.inputImage) {
      this.inputImage.alt = label;
      this.inputImage.hidden = !active || !source;
      if (active && source && this.inputSource !== source) {
        this.inputImage.src = source; this.inputSource = source;
      }
    }
    const title = this.panel.querySelector(".virtual-camera-preview-title");
    if (title) title.textContent = active ? label : "腕部相机 · 虚拟画面";
    this.panel.dataset.source = active ? identity : "virtual_scene";
  }

  private async startRealFeed():Promise<void>{
    if(this.realRequest)void agentClient.cancel(this.realRequest).catch(()=>undefined);
    const requestId=crypto.randomUUID();this.realRequest=requestId;
    try {
      await agentClient.realCameraPreview<RealFrame>(requestId,this.realSource,frame=>{
        if(this.realRequest!==requestId||this.tracking)return;
        const optionsKey=JSON.stringify([this.realSource,frame.cameras]);
        if(this.selector&&this.cameraOptionsKey!==optionsKey){
          const options=[new Option("自动选择真实相机","auto"),...frame.cameras.map(camera=>new Option(camera.name,camera.id))];
          if(!options.some(option=>option.value===this.realSource))options.push(new Option("所选相机（离线）",this.realSource));
          this.selector.replaceChildren(...options);this.selector.value=this.realSource;
          this.cameraOptionsKey=optionsKey;
        }
        const title=frame.status==="ready"?`真实相机 · ${frame.name}`:"真实相机 · 等待连接";
        this.setInputFrame(frame.image??null,true,title,"real_camera");
        if(this.panel){this.panel.title=frame.message??title;this.panel.dataset.cameraSource=frame.source??this.realSource;this.panel.dataset.cameraTimestamp=String(frame.timestamp_ns??0);}
      });
    } catch(error){if(this.realRequest===requestId&&this.panel)this.panel.title=String(error);}
  }

  private async follow(id:string):Promise<void>{
    if(this.realRequest){void agentClient.cancel(this.realRequest).catch(()=>undefined);this.realRequest="";}
    if(this.trackingId)void agentClient.cancel(this.trackingId).catch(()=>undefined);
    const requestId=crypto.randomUUID();this.trackingId=requestId;this.tracking=true;this.show();
    try {
      await agentClient.redTrackingPreview<TrackingFrame>(requestId,id,frame=>{
        if(this.trackingId!==requestId)return;
        const status=({tracking:"跟随中",centered:"已对准",searching:"等待目标",stopped:"已停止",failed:"已停止"} as Record<string,string>)[frame.status]??"等待目标";
        this.setInputFrame(frame.image??null,frame.physical,`${frame.physical?"真实相机":"虚拟相机"} · ${status}`,"red_tracking");
        if(!this.overlay){
          this.overlay=document.createElementNS("http://www.w3.org/2000/svg","svg");
          const top=this.selector?70:33;
          this.overlay.style.cssText=`position:absolute;left:0;top:${top}px;width:100%;height:calc(100% - ${top}px);pointer-events:none`;
          this.overlay.setAttribute("aria-label","红色目标位置");this.panel?.append(this.overlay);
        }
        const width=frame.width??640,height=frame.height??480;
        this.overlay.setAttribute("viewBox",`0 0 ${width} ${height}`);
        this.overlay.setAttribute("preserveAspectRatio","xMidYMid meet");
        this.overlay.replaceChildren();
        if(frame.found&&frame.box){
          const [x,y,w,h]=frame.box,rect=document.createElementNS("http://www.w3.org/2000/svg","rect");
          rect.setAttribute("x",String(x*width));rect.setAttribute("y",String(y*height));rect.setAttribute("width",String(w*width));rect.setAttribute("height",String(h*height));
          rect.setAttribute("fill","none");rect.setAttribute("stroke","#ef5656");rect.setAttribute("stroke-width","2");rect.setAttribute("vector-effect","non-scaling-stroke");
          this.overlay.append(rect);
        }
      });
    } catch(error) {
      if(this.trackingId===requestId&&this.panel)this.panel.title=String(error);
    } finally {
      if(this.trackingId===requestId){
        this.trackingId="";this.tracking=false;this.overlay?.remove();this.overlay=undefined;
        this.setInputFrame(null,false);if(this.realEnabled)void this.startRealFeed();else if(!this.configuredVisible)this.release();
      }
    }
  }

  private stopTracking():void {
    if(!this.tracking)return;
    const requestId=this.trackingId;this.trackingId="";this.tracking=false;
    if(requestId)void agentClient.cancel(requestId).catch(()=>undefined);
    this.overlay?.remove();this.overlay=undefined;this.setInputFrame(null,false);
    if(this.realEnabled)void this.startRealFeed();else if(!this.configuredVisible)this.release();
  }

  render(scene: THREE.Scene, camera: THREE.PerspectiveCamera): void {
    const renderer = this.renderer;
    if (!renderer || (this.inputMode&&!this.realEnabled)) return;
    renderer.render(scene, camera);
    // 开发桥保管认证令牌；最多 2 FPS，上一帧未上传时丢弃，避免积压。
    if (!agentClient.desktop || this.uploading || performance.now() - this.lastUpload < 500) return;
    this.lastUpload = performance.now();
    const image = renderer.domElement.toDataURL("image/jpeg", 0.8).split(",")[1];
    this.uploading = true;
    void agentClient.request({ action: "publish_camera_frame", image_base64: image })
      .then(() => { if (this.panel) { this.panel.dataset.frameStatus = "ready"; this.panel.title = "虚拟画面 API 已连接"; } })
      .catch(() => { if (this.panel) { this.panel.dataset.frameStatus = "unavailable"; this.panel.title = "相机未连接"; } })
      .finally(() => { this.uploading = false; });
  }

  dispose(): void {
    window.removeEventListener("table:red-tracking-start",this.trackingStart);
    window.removeEventListener("table:red-tracking-stop",this.trackingStop);
    if(this.realRequest)void agentClient.cancel(this.realRequest).catch(()=>undefined);
    this.realRequest="";this.realEnabled=false;
    if(this.trackingId)void agentClient.cancel(this.trackingId).catch(()=>undefined);
    this.trackingId="";this.tracking=false;this.release();
  }

  private release():void {
    this.renderer?.dispose();
    this.renderer?.forceContextLoss();
    this.panel?.remove();
    this.renderer = undefined;
    this.panel = undefined;
    this.inputImage = undefined; this.inputSource = ""; this.inputMode = false;
    this.overlay=undefined;
    this.selector=undefined;this.cameraOptionsKey="";
  }
}

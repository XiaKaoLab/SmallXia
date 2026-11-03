/** 功能：仅在显式显示时创建虚拟相机实时画面，隐藏时释放渲染资源。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import { agentClient } from "./chat/AgentClient";

export class VirtualCameraPreview {
  private uploading = false;
  private lastUpload = 0;
  private inputMode = false;
  private inputImage?: HTMLImageElement;
  private inputSource = "";
  private renderer: THREE.WebGLRenderer | undefined;
  private panel: HTMLElement | undefined;

  constructor(private readonly host: HTMLElement) {}

  setVisible(visible: boolean): void {
    if (!visible) { this.dispose(); return; }
    if (this.renderer) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(1);
    renderer.setSize(960, 720);
    renderer.domElement.setAttribute("aria-label", "虚拟腕部相机实时画面");
    const panel = document.createElement("section");
    panel.className = "virtual-camera-preview";
    const title = document.createElement("div");
    title.className = "virtual-camera-preview-title";
    title.textContent = "腕部相机 · 虚拟画面";
    const resize = document.createElement("button");
    resize.type="button";resize.className="virtual-camera-preview-resize";resize.textContent="展开";
    resize.setAttribute("aria-expanded","false");
    resize.addEventListener("click",()=>{
      const expanded=panel.classList.toggle("is-expanded");resize.textContent=expanded?"收起":"展开";
      resize.setAttribute("aria-expanded",String(expanded));
    });
    panel.append(title, resize, renderer.domElement);
    this.host.appendChild(panel);
    this.renderer = renderer;
    this.panel = panel;
  }

  setInputFrame(source: string | null, active: boolean, label = "腕部相机 · 推理输入", identity = "policy_input"): void {
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

  render(scene: THREE.Scene, camera: THREE.PerspectiveCamera): void {
    const renderer = this.renderer;
    if (!renderer || this.inputMode) return;
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
    this.renderer?.dispose();
    this.renderer?.forceContextLoss();
    this.panel?.remove();
    this.renderer = undefined;
    this.panel = undefined;
    this.inputImage = undefined; this.inputSource = ""; this.inputMode = false;
  }
}

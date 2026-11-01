/** 功能：仅在显式显示时创建虚拟相机实时画面，隐藏时释放渲染资源。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import { agentClient } from "./chat/AgentClient";

export class VirtualCameraPreview {
  private uploading = false;
  private lastUpload = 0;
  private renderer: THREE.WebGLRenderer | undefined;
  private panel: HTMLElement | undefined;

  constructor(private readonly host: HTMLElement) {}

  setVisible(visible: boolean): void {
    if (!visible) { this.dispose(); return; }
    if (this.renderer) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(320, 240);
    renderer.domElement.setAttribute("aria-label", "虚拟腕部相机实时画面");
    const panel = document.createElement("section");
    panel.className = "virtual-camera-preview";
    const title = document.createElement("div");
    title.className = "virtual-camera-preview-title";
    title.textContent = "腕部相机 · 虚拟画面";
    panel.append(title, renderer.domElement);
    this.host.appendChild(panel);
    this.renderer = renderer;
    this.panel = panel;
  }

  render(scene: THREE.Scene, camera: THREE.PerspectiveCamera): void {
    const renderer = this.renderer;
    if (!renderer) return;
    renderer.render(scene, camera);
    // 开发桥保管认证令牌；最多 2 FPS，上一帧未上传时丢弃，避免积压。
    if (!agentClient.desktop || this.uploading || performance.now() - this.lastUpload < 500) return;
    this.lastUpload = performance.now();
    const image = renderer.domElement.toDataURL("image/jpeg", 0.8).split(",")[1];
    this.uploading = true;
    void agentClient.request({ action: "publish_camera_frame", image_base64: image })
      .then(() => { if (this.panel) { this.panel.dataset.frameStatus = "ready"; this.panel.title = "虚拟画面 API 已连接"; } })
      .catch(() => { if (this.panel) { this.panel.dataset.frameStatus = "unavailable"; this.panel.title = "虚拟画面 API 不可用，请检查 core 服务"; } })
      .finally(() => { this.uploading = false; });
  }

  dispose(): void {
    this.renderer?.dispose();
    this.renderer?.forceContextLoss();
    this.panel?.remove();
    this.renderer = undefined;
    this.panel = undefined;
  }
}

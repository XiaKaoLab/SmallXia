/** 功能：仅在显式显示时创建虚拟相机实时画面，隐藏时释放渲染资源。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";

export class VirtualCameraPreview {
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
    this.renderer?.render(scene, camera);
  }

  dispose(): void {
    this.renderer?.dispose();
    this.renderer?.forceContextLoss();
    this.panel?.remove();
    this.renderer = undefined;
    this.panel = undefined;
  }
}

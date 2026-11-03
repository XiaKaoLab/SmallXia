/** 功能：只读采集同一渲染姿态的多视角图像及关节记录。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import type { URDFRobot } from "urdf-loader";

export class RobotObservation {
  static current: RobotObservation | undefined;
  constructor(private readonly renderer: THREE.WebGLRenderer, private readonly scene: THREE.Scene,
    private readonly state: () => { robot: URDFRobot | undefined; source: string; ready: boolean }) {
    RobotObservation.current = this;
  }
  capture(views: string[]) {
    const { robot, source, ready } = this.state();
    if (!ready || !robot) throw new Error("机械臂画面尚未准备好");
    const directions: Record<string, number[]> = { front: [0, -1, .45], side: [1, 0, .45], top: [0, 0, 1] };
    if (!Array.isArray(views) || !views.length || views.length > 3 || views.some(view => !directions[view])) throw new Error("视角仅支持 front、side、top");
    this.scene.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(robot);
    const center = bounds.getCenter(new THREE.Vector3());
    const radius = Math.max(bounds.getSize(new THREE.Vector3()).length() / 2, .15);
    const timestamp = new Date().toISOString();
    const joints = Object.fromEntries(Object.entries(robot.joints).filter(([, joint]) => joint.jointType === "revolute").map(([name, joint]) => [name, joint.jointValue[0]]));
    const size = 384, target = new THREE.WebGLRenderTarget(size, size);
    const previous = this.renderer.getRenderTarget();
    try {
      const images = views.map(view => {
        const camera = new THREE.PerspectiveCamera(40, 1, .001, 100);
        camera.up.set(0, view === "top" ? 1 : 0, view === "top" ? 0 : 1);
        camera.position.copy(center).add(new THREE.Vector3(...directions[view]).normalize().multiplyScalar(radius / Math.sin(Math.PI / 9) * 1.15));
        camera.lookAt(center);
        this.renderer.setRenderTarget(target);
        this.renderer.render(this.scene, camera);
        const pixels = new Uint8Array(size * size * 4);
        this.renderer.readRenderTargetPixels(target, 0, 0, size, size, pixels);
        const canvas = document.createElement("canvas"); canvas.width = size; canvas.height = size;
        const context = canvas.getContext("2d")!;
        const data = context.createImageData(size, size);
        for (let y = 0; y < size; y++) data.data.set(pixels.subarray((size - y - 1) * size * 4, (size - y) * size * 4), y * size * 4);
        context.putImageData(data, 0, 0);
        return { view, data_url: canvas.toDataURL("image/png"), width: size, height: size };
      });
      if (images.reduce((total, image) => total + image.data_url.length, 0) > 850000) throw new Error("截图内容过大，请减少视角后重试");
      return { timestamp, source, physical: false, unit: "rad", joints, images };
    } finally { this.renderer.setRenderTarget(previous); target.dispose(); }
  }
  dispose() { if (RobotObservation.current === this) RobotObservation.current = undefined; }
}

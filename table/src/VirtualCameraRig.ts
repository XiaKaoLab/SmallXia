/** 功能：将虚拟相机及视锥附着到 URDF 连杆并管理资源生命周期。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import type { URDFRobot } from "urdf-loader";

export interface VirtualCameraConfig {
  parent_link: string;
  position: [number, number, number];
  rotation: [number, number, number];
  fov: number;
}

export class VirtualCameraRig {
  private readonly mount = new THREE.Group();
  private readonly camera = new THREE.PerspectiveCamera(60, 4 / 3, 0.015, 0.25);
  private readonly helper = new THREE.CameraHelper(this.camera);
  private readonly body = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.025, 0.02),
    new THREE.MeshStandardMaterial({ color: 0x376b8c, roughness: 0.4 }));
  private readonly lens = new THREE.Mesh(new THREE.CylinderGeometry(0.009, 0.009, 0.012, 16),
    new THREE.MeshStandardMaterial({ color: 0x132d3e, metalness: 0.3, roughness: 0.2 }));
  private signature = "";

  constructor(scene: THREE.Scene) {
    this.mount.name = "virtual_camera_mount";
    this.body.position.z = 0.01;
    this.lens.rotation.x = Math.PI / 2;
    this.lens.position.z = -0.005;
    this.mount.add(this.body, this.lens, this.camera);
    this.helper.visible = false;
    scene.add(this.helper);
  }

  configure(robot: URDFRobot, config: VirtualCameraConfig | null): void {
    if (!config) { this.mount.removeFromParent(); this.helper.visible = false; this.signature = ""; return; }
    const signature = JSON.stringify(config);
    if (signature === this.signature) return;
    const parent = robot.links[config.parent_link];
    if (!parent || !Array.isArray(config.position) || !Array.isArray(config.rotation)
      || config.position.length !== 3 || config.rotation.length !== 3
      || !config.position.every((v) => Number.isFinite(v) && Math.abs(v) <= 2)
      || !config.rotation.every((v) => Number.isFinite(v) && Math.abs(v) <= Math.PI)
      || !Number.isFinite(config.fov) || config.fov < 10 || config.fov > 140) return;
    parent.add(this.mount);
    this.mount.position.set(...config.position);
    this.mount.rotation.set(...config.rotation, "ZYX");
    this.camera.fov = config.fov;
    this.camera.updateProjectionMatrix();
    this.helper.visible = true;
    this.signature = signature;
  }

  update(): void { if (this.helper.visible) { this.mount.updateWorldMatrix(true, true); this.helper.update(); } }

  dispose(): void {
    this.mount.removeFromParent();
    this.helper.removeFromParent(); this.helper.dispose();
    this.body.geometry.dispose(); this.body.material.dispose();
    this.lens.geometry.dispose(); this.lens.material.dispose();
  }
}

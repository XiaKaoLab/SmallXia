/** 功能：URDF 缺少相机支架时，按原腕部网格变换加载上游替换件 STL。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import type { URDFRobot, URDFVisual } from "urdf-loader";

export class WristCameraMount {
  private readonly group = new THREE.Group();
  private readonly material = new THREE.MeshStandardMaterial({ color: 0xcac35e, roughness: 0.65 });
  private original: URDFVisual | undefined;
  private originalVisible = true;
  private mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial> | undefined;
  private requested = false;
  private loading = false;
  private disposed = false;
  private failed = false;

  setVisible(robot: URDFRobot, visible: boolean): void {
    this.requested = visible;
    if (!visible) { this.restore(); return; }
    if (this.disposed || this.failed) return;
    const link = robot.links.gripper_link;
    if (!link) return;
    // URDF 已引用相机支架时不再叠加替换件。
    if (link.children.some((child) => /cam.*mount|mount.*cam/i.test(
      (child as URDFVisual).urdfNode?.querySelector("mesh")?.getAttribute("filename") ?? ""))) return;
    if (!this.original) {
      const original = link.children.find((child) =>
        (child as URDFVisual).urdfNode?.querySelector("mesh")?.getAttribute("filename")?.endsWith("wrist_roll_follower_so101_v1.stl"));
      if (!original) return;
      this.original = original as URDFVisual;
      this.originalVisible = original.visible;
      this.group.name = "wrist_camera_mount_stl";
      this.group.position.copy(original.position);
      this.group.quaternion.copy(original.quaternion);
      this.group.scale.copy(original.scale);
      link.add(this.group);
    }
    if (this.mesh) { this.original.visible = false; this.group.visible = true; return; }
    if (this.loading) return;
    this.loading = true;
    new STLLoader().load(`${import.meta.env.BASE_URL}robots/so101/camera/wrist_camera_mount_so101.stl`, (geometry) => {
      this.loading = false;
      if (this.disposed) { geometry.dispose(); return; }
      // 上游打印 STL 用毫米；原 URDF 网格以米为单位，保留 CAD 原点。
      geometry.scale(0.001, 0.001, 0.001);
      geometry.computeVertexNormals();
      this.mesh = new THREE.Mesh(geometry, this.material);
      this.group.add(this.mesh);
      if (this.requested && this.original) { this.original.visible = false; this.group.visible = true; }
      else this.restore();
    }, undefined, (error) => {
      this.loading = false; this.failed = true; this.restore();
      console.error("相机支架 STL 加载失败", error);
    });
  }

  private restore(): void {
    this.group.visible = false;
    if (this.original) this.original.visible = this.originalVisible;
  }

  dispose(): void {
    this.disposed = true;
    this.restore();
    this.group.removeFromParent();
    this.mesh?.geometry.dispose();
    this.material.dispose();
  }
}

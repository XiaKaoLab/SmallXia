/** 功能：加载 SO100/SO101 官方相机支架，在显示相机时替换原打印件。
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
  private replacesBody = true;
  private mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial> | undefined;
  private requested = false;
  private loading = false;
  private disposed = false;
  private failed = false;
  private robotId = "";
  private generation = 0;

  setVisible(robot: URDFRobot, visible: boolean): void {
    this.requested = visible;
    if (!visible) { this.restore(); return; }
    if (this.robotId !== robot.uuid) {
      this.restore(); this.group.removeFromParent(); this.group.clear();
      this.mesh?.geometry.dispose(); this.mesh = undefined; this.original = undefined;
      this.loading = false; this.failed = false; this.robotId = robot.uuid; this.generation++;
    }
    if (this.disposed || this.failed) return;
    const link = robot.links.gripper_link;
    if (!link) return;
    // URDF 已引用相机支架时不再叠加替换件。
    if (link.children.some((child) => /cam.*mount|mount.*cam/i.test(
      (child as URDFVisual).urdfNode?.querySelector("mesh")?.getAttribute("filename") ?? ""))) return;
    if (!this.original) {
      const so100 = robot.robotName === "so100_mid_calib";
      this.replacesBody = !so100;
      const filename = so100 ? "Fixed_Jaw.stl" : "wrist_roll_follower_so101_v1.stl";
      const original = link.children.find((child) =>
        (child as URDFVisual).urdfNode?.querySelector("mesh")?.getAttribute("filename")?.endsWith(filename));
      if (!original) return;
      this.original = original as URDFVisual;
      this.originalVisible = original.visible;
      this.group.name = "wrist_camera_mount_stl";
      this.group.position.copy(original.position);
      this.group.quaternion.copy(original.quaternion);
      this.group.scale.copy(original.scale);
      if (so100) {
        // SO100 打印坐标到 Fixed_Jaw 的局部坐标；保留 CAD 原点，不按包围盒居中。
        this.group.position.add(new THREE.Vector3(0, -.001, 0).applyQuaternion(original.quaternion));
        this.group.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2));
      }
      link.add(this.group);
    }
    if (this.mesh) { this.show(); return; }
    if (this.loading) return;
    this.loading = true;
    const generation = this.generation;
    const model = robot.robotName === "so100_mid_calib" ? "so100" : "so101";
    const filename = model === "so100" ? "camera_support_so100.stl" : "wrist_camera_mount_so101.stl";
    new STLLoader().load(`${import.meta.env.BASE_URL}robots/${model}/camera/${filename}`, (geometry) => {
      if (generation !== this.generation || this.disposed) { geometry.dispose(); return; }
      this.loading = false;
      // 上游打印 STL 用毫米；原 URDF 网格以米为单位，保留 CAD 原点。
      geometry.scale(0.001, 0.001, 0.001);
      geometry.computeVertexNormals();
      this.mesh = new THREE.Mesh(geometry, this.material);
      this.group.add(this.mesh);
      if (this.requested && this.original) this.show();
      else this.restore();
    }, undefined, (error) => {
      if (generation !== this.generation || this.disposed) return;
      this.loading = false; this.failed = true; this.restore();
      console.error("相机支架 STL 加载失败", error);
    });
  }

  private show(): void {
    if (this.original) this.original.visible = this.replacesBody ? false : this.originalVisible;
    this.group.visible = true;
  }

  private restore(): void {
    this.group.visible = false;
    if (this.original) this.original.visible = this.originalVisible;
  }

  dispose(): void {
    this.disposed = true;
    this.generation++;
    this.restore();
    this.group.removeFromParent();
    this.mesh?.geometry.dispose();
    this.material.dispose();
  }
}

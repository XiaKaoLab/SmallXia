/** 功能：基于 URDF 原始视觉网格限制关节路径，阻止非相邻连杆穿模及穿过底座平面。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import { MeshBVH } from "three-mesh-bvh";
import type { URDFRobot, URDFVisual } from "urdf-loader";

interface Collider { link: string; mesh: THREE.Mesh; geometry: THREE.BufferGeometry; bvh: MeshBVH; box: THREE.Box3 }
export interface PoseLimitResult { pose: Record<string, number>; blocked: boolean; reason: string }

export class ModelPoseGuard {
  private readonly colliders: Collider[] = [];
  private readonly adjacent = new Set<string>();
  private readonly transform = new THREE.Matrix4();
  private readonly floor: number;
  private lastSafe: Record<string, number>;

  constructor(private readonly robot: URDFRobot) {
    for (const joint of Object.values(robot.joints)) {
      const parent = joint.urdfNode?.querySelector("parent")?.getAttribute("link");
      const child = joint.urdfNode?.querySelector("child")?.getAttribute("link");
      if (parent && child) this.adjacent.add(this.key(parent, child));
    }
    for (const [link, object] of Object.entries(robot.links)) {
      for (const visual of object.children) {
        if (!(visual as URDFVisual).isURDFVisual) continue;
        visual.traverse((child) => {
          const mesh = child as THREE.Mesh;
          if (!mesh.isMesh || !mesh.geometry?.getAttribute("position")) return;
          const geometry = mesh.geometry.clone();
          const bvh = new MeshBVH(geometry);
          geometry.boundsTree = bvh;
          geometry.computeBoundingBox();
          this.colliders.push({ link, mesh, geometry, bvh, box: new THREE.Box3() });
        });
      }
    }
    if (!this.colliders.length) throw new Error("碰撞网格未加载，暂不能移动");
    robot.updateMatrixWorld(true);
    const baseBounds = new THREE.Box3();
    for (const c of this.colliders.filter((item) => item.link === "base_link")) {
      baseBounds.union(c.box.copy(c.geometry.boundingBox!).applyMatrix4(c.mesh.matrixWorld));
    }
    this.floor = baseBounds.min.z;
    this.lastSafe = this.capture();
    const collision = this.collision();
    if (collision) throw new Error(`初始姿态不可用：${collision}`);
  }

  private key(a: string, b: string): string { return [a, b].sort().join("|"); }
  private capture(): Record<string, number> {
    return Object.fromEntries(Object.entries(this.robot.joints).filter(([, joint]) => joint.jointType === "revolute")
      .map(([name, joint]) => [name, joint.jointValue[0]]));
  }
  private apply(pose: Record<string, number>): void { this.robot.setJointValues(pose); this.robot.updateMatrixWorld(true); }

  private collision(): string {
    for (const c of this.colliders) {
      c.box.copy(c.geometry.boundingBox!).applyMatrix4(c.mesh.matrixWorld);
      if (c.link !== "base_link" && c.box.min.z < this.floor - 0.001) return `${c.link} 触及底座平面`;
    }
    for (let i = 0; i < this.colliders.length; i++) {
      const a = this.colliders[i];
      for (let j = i + 1; j < this.colliders.length; j++) {
        const b = this.colliders[j];
        if (a.link === b.link || this.adjacent.has(this.key(a.link, b.link)) || !a.box.intersectsBox(b.box)) continue;
        this.transform.copy(a.mesh.matrixWorld).invert().multiply(b.mesh.matrixWorld);
        if (a.bvh.intersectsGeometry(b.geometry, this.transform)) return `${a.link} 与 ${b.link} 相碰`;
      }
    }
    return "";
  }

  limit(desired: Record<string, number>): PoseLimitResult {
    let start = this.capture();
    if (this.collision()) { start = { ...this.lastSafe }; this.apply(start); }
    this.lastSafe = { ...start };
    for (const [name, angle] of Object.entries(desired)) {
      const joint = this.robot.joints[name];
      if (!joint || !Number.isFinite(angle) || angle < joint.limit.lower || angle > joint.limit.upper) {
        return { pose: start, blocked: true, reason: "目标超出关节限位" };
      }
    }
    const target = { ...start, ...desired };
    const interpolate = (fraction: number) => Object.fromEntries(Object.keys(start).map((name) =>
      [name, start[name] + (target[name] - start[name]) * fraction]));
    const steps = Math.max(1, Math.ceil(Math.max(...Object.keys(start).map((name) => Math.abs(target[name] - start[name]))) / (Math.PI / 180)));
    let fraction = 0;
    let reason = "";
    try {
      for (let step = 1; step <= steps; step++) {
        this.apply(interpolate(step / steps));
        reason = this.collision();
        if (reason) {
          let low = fraction, high = step / steps;
          for (let refine = 0; refine < 6; refine++) {
            const middle = (low + high) / 2;
            this.apply(interpolate(middle));
            if (this.collision()) high = middle; else low = middle;
          }
          fraction = Math.max(0, low - 0.0001);
          break;
        }
        fraction = step / steps;
      }
      return { pose: interpolate(fraction), blocked: !!reason, reason };
    } finally { this.apply(start); }
  }

  dispose(): void { for (const c of this.colliders) c.geometry.dispose(); }
}

/** 功能：在现有三维场景展示训练环境 1 的实际物理状态。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import type { URDFRobot } from "urdf-loader";

interface Snapshot { joint_positions: Record<string, number>; ball_position: number[]; ball_radius: number }
export class BallTrainingScene {
  private readonly ball = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16), new THREE.MeshStandardMaterial({ color: "#f17a46", roughness: .5 }));
  private snapshot: Snapshot | null = null;
  private readonly receive = (event: Event) => {
    this.snapshot = (event as CustomEvent<Snapshot | null>).detail;
    this.ball.visible = !!this.snapshot;
    if (this.snapshot) {
      this.ball.position.fromArray(this.snapshot.ball_position);
      this.ball.scale.setScalar(this.snapshot.ball_radius);
    }
  };
  constructor(scene: THREE.Scene) {
    this.ball.visible = false;
    scene.add(this.ball);
    window.addEventListener("table:ball-training", this.receive);
  }
  get active(): boolean { return !!this.snapshot; }
  update(robot: URDFRobot): void {
    if (this.snapshot) robot.setJointValues(this.snapshot.joint_positions);
  }
  dispose(): void {
    window.removeEventListener("table:ball-training", this.receive);
    this.ball.removeFromParent(); this.ball.geometry.dispose(); this.ball.material.dispose();
  }
}

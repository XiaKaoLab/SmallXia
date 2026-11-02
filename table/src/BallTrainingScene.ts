/** 功能：按真实环境数量同台渲染机械臂与小球，逐帧插值并独立订阅训练预览。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import type { URDFRobot } from "urdf-loader";
import { TrainingPreviewClient, type TrainingPreview, type TrainingSnapshot } from "./TrainingPreviewClient";

interface Instance { robot: URDFRobot; ball: THREE.Mesh; offset: THREE.Vector3; episode?: number }
export class BallTrainingScene {
  private readonly group = new THREE.Group();
  private readonly sphere = new THREE.SphereGeometry(1, 20, 12);
  private readonly material = new THREE.MeshStandardMaterial({ color: "#f17a46", roughness: .5 });
  private readonly floorGeometry = new THREE.PlaneGeometry(.52, .52);
  private readonly floorMaterial = new THREE.MeshStandardMaterial({ color: "#d6e2dc", side: THREE.DoubleSide, roughness: 1 });
  private snapshots: TrainingSnapshot[] = [];
  private instances: Instance[] = [];
  private source?: URDFRobot;
  private version = "";
  private jobId = "";
  private changed = false;
  private frozen = false;
  private readonly playback = (event: Event) => {
    const detail = (event as CustomEvent<{ jobId: string; paused: boolean }>).detail;
    if (detail.jobId === this.jobId) this.frozen = detail.paused;
  };
  private previewKind = "";
  private inputFrame: string | null = null;
  private readonly client = new TrainingPreviewClient(frame => this.receiveFrame(frame));
  private readonly close = (event: Event) => {
    if ((event as CustomEvent).detail === null) { this.snapshots = []; this.clear(); }
  };

  constructor(scene: THREE.Scene, private readonly fit: (count: number) => void) {
    window.addEventListener("table:inference-playback", this.playback);
    this.group.name = "training_environments";
    scene.add(this.group);
    window.addEventListener("table:ball-training", this.close);
  }

  private receiveFrame(frame: TrainingPreview): void {
    if (this.frozen && frame.job_id === this.jobId) return;
    const version = `${frame.job_id}:${frame.timestamp_ns}`;
    if (version === this.version) return;
    this.version = version;
    if (this.jobId !== frame.job_id) this.frozen = false;
    this.changed ||= this.jobId !== frame.job_id;
    this.jobId = frame.job_id;
    this.previewKind = frame.kind ?? "";
    const image = frame.camera_frame?.data_url;
    this.inputFrame = image?.startsWith("data:image/png;base64,") && image.length < 200000 ? image : null;
    this.snapshots = frame.snapshots.filter(item => item.ball_position?.length === 3
      && item.ball_position.every(Number.isFinite) && Number.isFinite(item.ball_radius)
      && Object.values(item.joint_positions).every(Number.isFinite));
  }

  get active(): boolean { return this.snapshots.length > 0; }
  get inferenceCamera(): boolean { return this.previewKind === "ball_onnx_rollout"; }
  get cameraFrame(): string | null { return this.inputFrame; }
  get count(): number { return this.instances.length; }

  private clear(): void {
    for (const instance of this.instances) {
      if (instance.robot !== this.source) instance.robot.removeFromParent();
    }
    this.group.clear(); this.instances = [];
    if (this.source) this.source.position.set(0, 0, 0);
  }

  private layout(robot: URDFRobot): void {
    this.clear(); this.source = robot;
    const count = this.snapshots.length, columns = Math.ceil(Math.sqrt(count)), rows = Math.ceil(count / columns);
    for (let index = 0; index < count; index++) {
      const offset = new THREE.Vector3((index % columns - (columns - 1) / 2) * .62, (Math.floor(index / columns) - (rows - 1) / 2) * .62, 0);
      const arm = index === 0 ? robot : robot.clone() as URDFRobot;
      arm.position.copy(offset);
      if (index > 0) {
        arm.name = `training_arm_${index + 1}`;
        arm.getObjectByName("virtual_camera_mount")?.removeFromParent();
        this.group.add(arm);
      }
      const ball = new THREE.Mesh(this.sphere, this.material);
      ball.name = `training_ball_${index + 1}`;
      ball.position.fromArray(this.snapshots[index].ball_position).add(offset);
      ball.scale.setScalar(this.snapshots[index].ball_radius);
      const floor = new THREE.Mesh(this.floorGeometry, this.floorMaterial);
      floor.position.copy(offset); floor.position.z = this.snapshots[index].floor_z ?? -.004;
      this.group.add(ball, floor);
      this.instances.push({ robot: arm, ball, offset, episode: this.snapshots[index].episode_index });
    }
    this.fit(count); this.changed = false;
  }

  update(robot: URDFRobot, dt: number): void {
    if (!this.active || this.frozen) return;
    const fresh = this.changed || this.instances.length !== this.snapshots.length || this.source !== robot;
    if (fresh) this.layout(robot);
    const alpha = fresh ? 1 : 1 - Math.exp(-dt / .09);
    this.instances.forEach((instance, index) => {
      const snapshot = this.snapshots[index];
      const reset = snapshot.episode_index !== undefined && snapshot.episode_index !== instance.episode;
      const blend = reset ? 1 : alpha;
      instance.episode = snapshot.episode_index;
      for (const [name, target] of Object.entries(snapshot.joint_positions)) {
        const joint = instance.robot.joints[name];
        if (joint) joint.setJointValue(THREE.MathUtils.lerp(joint.jointValue[0], target, blend));
      }
      instance.ball.position.lerp(new THREE.Vector3().fromArray(snapshot.ball_position).add(instance.offset), blend);
      instance.ball.scale.setScalar(snapshot.ball_radius);
    });
  }

  dispose(): void {
    this.client.dispose(); window.removeEventListener("table:inference-playback", this.playback); window.removeEventListener("table:ball-training", this.close);
    this.clear(); this.group.removeFromParent();
    this.sphere.dispose(); this.material.dispose(); this.floorGeometry.dispose(); this.floorMaterial.dispose();
  }
}

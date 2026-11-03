/** 功能：按真实环境数量同台渲染机械臂与小球，逐帧插值并独立订阅训练预览。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { TextCubeObjects } from "./TextCubeObjects";
import * as THREE from "three";
import { RobotAssetLoader } from "./RobotAssetLoader";
import { WristCameraMount } from "./WristCameraMount";
import type { URDFRobot } from "urdf-loader";
import { TrainingPreviewClient, type TrainingPreview, type TrainingSnapshot } from "./TrainingPreviewClient";

interface Instance { robot: URDFRobot; ball: THREE.Mesh; offset: THREE.Vector3; episode?: number; cubes?: TextCubeObjects }
export class BallTrainingScene {
  private readonly group = new THREE.Group();
  private readonly sphere = new THREE.SphereGeometry(1, 20, 12);
  private readonly material = new THREE.MeshStandardMaterial({ color: "#f17a46", roughness: .5 });
  private readonly floorGeometry = new THREE.PlaneGeometry(.52, .52);
  private readonly floorMaterial = new THREE.MeshStandardMaterial({ color: "#d6e2dc", side: THREE.DoubleSide, roughness: 1 });
  private snapshots: TrainingSnapshot[] = [];
  private instances: Instance[] = [];
  private brackets: WristCameraMount[] = [];
  private source?: URDFRobot;
  private template?: URDFRobot;
  private loadingTemplate = false;
  private disposed = false;
  get cameraRobot(): URDFRobot | undefined { return this.template; }
  private version = "";
  private jobId = "";
  private changed = false;
  private frozen = false;
  private hidden = false;
  private readonly playback = (event: Event) => {
    const detail = (event as CustomEvent<{ jobId: string; paused: boolean }>).detail;
    if (detail.jobId === this.jobId) this.frozen = detail.paused;
  };
  private previewKind = "";
  private inputFrame: string | null = null;
  cameraTitle = "腕部相机";
  cameraSource = "policy_input";
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
    this.inputFrame = image?.startsWith("data:image/png;base64,") && image.length < 2000000 ? image : null;
    const camera = frame.camera_frame;
    this.cameraSource = camera?.source ?? "policy_input";
    const name = camera?.camera === "letter_overhead" ? "俯视相机" : "腕部相机";
    const purpose = camera?.source === "ocr_observation" ? "OCR 画面" : (this.inferenceCamera ? "推理输入" : "训练输入");
    const resolution = camera?.width && camera?.height ? ` · ${camera.width}×${camera.height}` : "";
    this.cameraTitle = `${name} · ${purpose}${resolution}`;
    this.snapshots = frame.snapshots.filter(item => item.ball_position?.length === 3
      && item.ball_position.every(Number.isFinite) && Number.isFinite(item.ball_radius)
      && Object.values(item.joint_positions).every(Number.isFinite));
  }

  setHidden(hidden: boolean): void {
    if (this.hidden === hidden) return;
    this.hidden = hidden; this.group.visible = !hidden;
    if (hidden) this.source?.position.set(0, 0, 0);
    else this.changed = true;
  }

  get active(): boolean { return this.snapshots.length > 0; }
  get inferenceCamera(): boolean { return this.previewKind === "ball_onnx_rollout"; }
  get cameraVisible(): boolean { return this.active; }
  get cameraFrame(): string | null { return this.inputFrame; }
  get count(): number { return this.instances.length; }

  private clear(): void {
    this.brackets.forEach(bracket => bracket.dispose()); this.brackets = [];
    for (const instance of this.instances) {
      instance.cubes?.dispose();
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
      if (index === 0 && robot === this.template) this.group.add(arm);
      arm.position.copy(offset);
      if (index > 0) {
        arm.name = `training_arm_${index + 1}`;
        arm.getObjectByName("virtual_camera_mount")?.removeFromParent();
        arm.getObjectByName("wrist_camera_mount_stl")?.removeFromParent();
        const bracket = new WristCameraMount();
        bracket.setVisible(arm, true); this.brackets.push(bracket);
        this.group.add(arm);
      }
      const ball = new THREE.Mesh(this.sphere, this.material);
      ball.name = `training_ball_${index + 1}`;
      ball.position.fromArray(this.snapshots[index].ball_position).add(offset);
      ball.scale.setScalar(this.snapshots[index].ball_radius);
      const floor = new THREE.Mesh(this.floorGeometry, this.floorMaterial);
      floor.position.copy(offset); floor.position.z = this.snapshots[index].floor_z ?? -.004;
      this.group.add(ball, floor);
      const cubes = this.snapshots[index].objects?.length ? new TextCubeObjects() : undefined;
      if (cubes) { this.group.add(cubes.group); cubes.update(this.snapshots[index].objects!, offset); ball.visible=false; }
      this.instances.push({ robot: arm, ball, offset, cubes, episode: this.snapshots[index].episode_index });
    }
    this.fit(count); this.changed = false;
  }

  update(robot: URDFRobot, dt: number): void {
    if (!this.active || this.frozen) return;
    // 已有抓球策略使用 SO-101，不将其动作套到 SO-100 的几何上。
    if (!this.template) {
      if (!this.loadingTemplate) {
        this.loadingTemplate = true;
        void new RobotAssetLoader().load(`${import.meta.env.BASE_URL}robots/so101/so101_new_calib.urdf`).then(template => {
          if (this.disposed) { this.releaseTemplate(template); return; }
          this.template = template; this.changed = true;
        }).catch(error => console.error("训练模型加载失败", error));
      }
      return;
    }
    robot = this.template;
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
      if (snapshot.objects && instance.cubes) instance.cubes.update(snapshot.objects, instance.offset);
      instance.ball.position.lerp(new THREE.Vector3().fromArray(snapshot.ball_position).add(instance.offset), blend);
      instance.ball.scale.setScalar(snapshot.ball_radius);
    });
  }

  private releaseTemplate(robot: URDFRobot): void {
    robot.traverse(object => {
      const mesh = object as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.geometry.dispose();
      (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).forEach(material => material.dispose());
    });
  }

  dispose(): void {
    this.disposed = true;
    this.client.dispose(); window.removeEventListener("table:inference-playback", this.playback); window.removeEventListener("table:ball-training", this.close);
    this.clear(); this.group.removeFromParent();
    if (this.template) this.releaseTemplate(this.template);
    this.sphere.dispose(); this.material.dispose(); this.floorGeometry.dispose(); this.floorMaterial.dispose();
  }
}

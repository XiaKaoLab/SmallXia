/** 功能：管理机械臂 URDF、场景和交互生命周期。
 * Created on 2026-11-01; Updated on 2026-11-04
 * @author: https://github.com/Linmoqian
 */
import { CoordinateCalibrationDisplay } from "./CoordinateCalibrationDisplay";
import { HardwareControlPreview } from "./HardwareControlPreview";
import { QiLingSpeechBubble } from "./QiLingSpeechBubble";
import { RobotObservation } from "./RobotObservation";
import { CameraCalibrationDisplay } from "./CameraCalibrationDisplay";
import { HardwareAlignmentDisplay } from "./HardwareAlignmentDisplay";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import URDFLoader from "urdf-loader";
import type { URDFRobot } from "urdf-loader";
import { ModelPoseGuard } from "./ModelPoseGuard";
import { jointPreview } from "./JointPreview";
import { SO101_WRIST_CAMERA_PRESET } from "./CameraPreset";
import { VirtualCameraRig, type VirtualCameraConfig } from "./VirtualCameraRig";
import { ModelMotionClient } from "./ModelMotionClient";
import { BallTrainingScene } from "./BallTrainingScene";

export class RobotViewer {
  private readonly scene = new THREE.Scene();
  private readonly training = new BallTrainingScene(this.scene, count => this.fitTraining(count));
  private readonly camera = new THREE.PerspectiveCamera(35, 1, 0.001, 100);
  private readonly renderer = new THREE.WebGLRenderer({ antialias: true });
  private readonly controls: OrbitControls;
  private readonly observer: ResizeObserver;
  private disposed = false;
  private modelReady = false;
  private robot: URDFRobot | undefined;
  private poseGuard: ModelPoseGuard | undefined;
  private targets: Record<string, number> = {};
  private modelCamera: VirtualCameraConfig | null = null;
  private readonly clock = new THREE.Clock();
  private readonly cameraRig: VirtualCameraRig;
  private readonly coordinateCalibration: CoordinateCalibrationDisplay;
  private readonly alignment: HardwareAlignmentDisplay;
  private readonly observation: RobotObservation;
  private readonly cameraCalibration: CameraCalibrationDisplay;
  private readonly spiritSpeech: QiLingSpeechBubble;
  private readonly controlFeedback: HardwareControlPreview;
  private alignmentVisible = false;
  private playbackId = "";
  private playbackPaused = false;
  private readonly stopPreview: () => void;
  private readonly motion = new ModelMotionClient((positions, camera, playback) => {
    this.playbackPaused = playback?.status === "paused";
    if (playback && ["running", "paused"].includes(playback.status) && (playback.id !== this.playbackId || this.training.active)) {
      if (playback.id !== this.playbackId) jointPreview.confirm(positions, jointPreview.revision);
      this.playbackId = playback.id;
      window.dispatchEvent(new CustomEvent("table:ball-training", { detail: null }));
    }
    this.modelCamera = camera;
    if (this.training.active || this.alignment?.positions || this.controlFeedback?.positions) return;
    this.setJointTargets(jointPreview.reconcile(positions));
    if (this.robot) this.cameraRig.configure(this.robot, camera);
  });

  constructor(private readonly host: HTMLElement) {
    this.controlFeedback = new HardwareControlPreview(host);
    this.observation = new RobotObservation(this.renderer, this.scene, () => ({
      robot: this.training.active && !this.alignment.positions && !this.controlFeedback.positions ? this.training.cameraRobot ?? undefined : this.robot,
      source: this.alignment.positions || this.controlFeedback.positions ? "hardware_mapped_render" : this.training.active ? "training_render_first_environment" : "simulation_render",
      ready: this.modelReady,
    }));
    this.alignment = new HardwareAlignmentDisplay(host);
    this.coordinateCalibration = new CoordinateCalibrationDisplay(host);
    this.cameraCalibration = new CameraCalibrationDisplay(host);
    this.spiritSpeech = new QiLingSpeechBubble(host);
    this.cameraRig = new VirtualCameraRig(this.scene, host);
    this.stopPreview = jointPreview.subscribe((name, angle) => {
      const joint = this.robot?.joints[name];
      if (!joint || !this.poseGuard) return joint?.jointValue[0] ?? 0;
      const result = this.poseGuard.limit({ [name]: angle });
      this.robot!.setJointValues(result.pose);
      this.targets = { ...result.pose };
      if (result.blocked) window.dispatchEvent(new CustomEvent("table:pose-limit", { detail: result.reason }));
      return result.pose[name];
    });
    this.scene.background = new THREE.Color("#e8edf0");
    this.camera.up.set(0, 0, 1);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.domElement.setAttribute("aria-label", "SO-ARM-101 机械臂模型");
    host.appendChild(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.enablePan = false;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x71808b, 2.5));
    const key = new THREE.DirectionalLight(0xffffff, 3);
    key.position.set(2, -2, 4);
    this.scene.add(key);
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(host);
    this.resize();
    this.renderer.setAnimationLoop(() => {
      this.updateJoints(Math.min(this.clock.getDelta(), 0.05));
      if (this.robot) jointPreview.displayed = Object.fromEntries(Object.entries(this.robot.joints).map(([name, joint]) => [name, joint.jointValue[0]]));
      this.cameraRig.update();
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
      const speakingRobot = this.training.active && !this.controlFeedback.positions && !this.alignment.positions ? this.training.cameraRobot : this.robot;
      this.spiritSpeech.update(speakingRobot?.links.gripper_link ?? speakingRobot, this.camera);
      this.cameraRig.renderPreview();
    });
    const manager = new THREE.LoadingManager();
    const loader = new URDFLoader(manager);
    loader.parseCollision = false;
    const meshes: Promise<void>[] = [];
    // 请求去重时 LoadingManager 可能先结束；以每个网格回调为准。
    loader.loadMeshCb = (path, meshManager, material, done) => {
      meshes.push(new Promise<void>((resolve, reject) => {
        loader.defaultMeshLoader(path, meshManager, material, (mesh, error) => {
          if (error) { reject(error); return; }
          done(mesh); resolve();
        });
      }));
    };
    manager.onError = (url) => console.error("机械臂资源加载失败", url);
    loader.load(`${import.meta.env.BASE_URL}robots/so100/so100_mid_calib.urdf`, (robot) => {
      this.robot = robot;
      this.scene.add(robot);
      void Promise.all(meshes).then(() => {
        if (this.disposed) { this.release(robot); return; }
        this.modelReady = true;
        robot.updateMatrixWorld(true);
        try { this.poseGuard = new ModelPoseGuard(robot); }
        catch (error) { console.error(error); window.dispatchEvent(new CustomEvent("table:pose-limit", { detail: String(error) })); }
        const bounds = new THREE.Box3().setFromObject(robot);
        const center = bounds.getCenter(new THREE.Vector3());
        const radius = Math.max(bounds.getSize(new THREE.Vector3()).length() / 2, 0.1);
        const distance = radius / Math.sin(THREE.MathUtils.degToRad(17.5));
        this.controls.target.copy(center);
        this.camera.position.copy(center).add(new THREE.Vector3(1, -1.4, 0.9).normalize().multiplyScalar(distance * 1.2));
        this.controls.minDistance = radius * 0.4;
        this.controls.maxDistance = distance * 5;
        this.camera.near = radius / 100;
        this.camera.far = distance * 20;
        this.camera.updateProjectionMatrix();
        this.controls.update();
      }).catch((error) => console.error("机械臂网格加载失败", error));
    }, undefined, (error) => console.error("机械臂 URDF 加载失败", error));
  }

  private setJointTargets(positions: Record<string, number>): void {
    if (!this.robot || !positions || typeof positions !== "object") return;
    const names = Object.keys(this.robot.joints).filter((name) => this.robot!.joints[name].jointType === "revolute");
    if (Object.keys(positions).length !== names.length) return;
    for (const name of names) {
      const value = positions[name];
      const { lower, upper } = this.robot.joints[name].limit;
      if (!Number.isFinite(value) || value < lower || value > upper) return;
    }
    if (!this.poseGuard) return;
    const result = this.poseGuard.limit(positions);
    this.targets = { ...result.pose };
  }

  private fitTraining(count: number): void {
    const columns = Math.ceil(Math.sqrt(count)), rows = Math.ceil(count / columns);
    const radius = Math.sqrt((columns * .62) ** 2 + (rows * .62) ** 2 + .5 ** 2) / 2;
    const vertical = THREE.MathUtils.degToRad(this.camera.fov);
    const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * this.camera.aspect);
    const distance = radius / Math.sin(Math.min(vertical, horizontal) / 2) * 1.15;
    this.controls.target.set(0, 0, .15);
    this.camera.position.copy(this.controls.target).add(new THREE.Vector3(1, -1.4, 1.2).normalize().multiplyScalar(distance));
    this.controls.maxDistance = distance * 4;
    this.camera.far = Math.max(100, distance * 10);
    this.camera.updateProjectionMatrix(); this.controls.update();
    this.host.dataset.trainingEnvs = String(count);
  }

  private updateJoints(dt: number): void {
    if (!this.robot || !this.modelReady) return;
    const hardwarePositions=this.controlFeedback.positions??this.alignment.positions;
    this.training.setHidden(hardwarePositions !== null);
    this.robot.visible = true;
    if (hardwarePositions && this.poseGuard) {
      if (!this.alignmentVisible) { this.fitTraining(1); this.alignmentVisible = true; }
      const desired = Object.fromEntries(Object.entries(hardwarePositions).map(([name, angle]) => {
        const joint = this.robot!.joints[name];
        return [name, joint ? Math.max(joint.limit.lower, Math.min(joint.limit.upper, angle)) : angle];
      }));
      const pose = this.poseGuard.limit(desired);
      this.robot.setJointValues(pose.pose);
      this.robot.position.set(0, 0, 0);
      this.cameraRig.configure(this.robot, this.modelCamera);
      this.cameraRig.setInferenceFrame(null, false);
      return;
    }
    this.alignmentVisible = false;
    if (this.training.active) {
      this.training.update(this.robot, dt);
      this.robot.visible = false;
      const trainingRobot = this.training.cameraRobot;
      if (!trainingRobot) return;
      this.cameraRig.configure(trainingRobot, this.training.cameraVisible ? SO101_WRIST_CAMERA_PRESET : this.modelCamera);
      this.cameraRig.setInferenceFrame(this.training.cameraFrame, this.training.cameraFrame !== null, this.training.cameraTitle, this.training.cameraSource);
      return;
    }
    this.cameraRig.configure(this.robot, this.modelCamera);
    this.cameraRig.setInferenceFrame(null, false);
    if (this.playbackPaused) return;
    if (!this.poseGuard || !Object.keys(this.targets).length) return;
    if (Object.entries(this.targets).every(([name, target]) => Math.abs(this.robot!.joints[name].jointValue[0] - target) < 1e-8)) return;
    const next = Object.fromEntries(Object.entries(this.targets).map(([name, target]) => {
      const joint = this.robot!.joints[name];
      const current = joint.jointValue[0];
      const step = Math.min(0.25, joint.limit.velocity) * dt;
      return [name, current + Math.max(-step, Math.min(step, target - current))];
    }));
    const result = this.poseGuard.limit(next);
    this.robot.setJointValues(result.pose);
    if (result.blocked) this.targets = { ...result.pose };
  }

  private resize(): void {
    const width = Math.max(this.host.clientWidth, 1);
    const height = Math.max(this.host.clientHeight, 1);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  private release(object: THREE.Object3D): void {
    object.traverse((child) => {
      if (!(child as THREE.Mesh).isMesh) return;
      const mesh = child as THREE.Mesh;
      mesh.geometry.dispose();
      (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).forEach((material) => material.dispose());
    });
  }

  dispose(): void {
    this.disposed = true;
    this.observation.dispose();
    this.motion.dispose();
    this.cameraCalibration.dispose();
    this.spiritSpeech.dispose();
    this.controlFeedback.dispose();
    this.alignment.dispose();
    this.coordinateCalibration.dispose();
    this.training.dispose();
    this.stopPreview();
    this.poseGuard?.dispose();
    this.observer.disconnect();
    this.renderer.setAnimationLoop(null);
    this.controls.dispose();
    this.cameraRig.dispose();
    this.release(this.scene);
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}


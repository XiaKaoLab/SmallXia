/** 功能：管理机械臂 URDF、场景和交互生命周期。
 * Created on 2026-11-01; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import URDFLoader from "urdf-loader";
import type { URDFRobot } from "urdf-loader";
import { VirtualCameraRig } from "./VirtualCameraRig";
import { ModelMotionClient } from "./ModelMotionClient";

export class RobotViewer {
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(35, 1, 0.001, 100);
  private readonly renderer = new THREE.WebGLRenderer({ antialias: true });
  private readonly controls: OrbitControls;
  private readonly observer: ResizeObserver;
  private disposed = false;
  private robot: URDFRobot | undefined;
  private targets: Record<string, number> = {};
  private readonly clock = new THREE.Clock();
  private readonly cameraRig: VirtualCameraRig;
  private readonly motion = new ModelMotionClient((positions, camera) => {
    this.setJointTargets(positions);
    if (this.robot) this.cameraRig.configure(this.robot, camera);
  });

  constructor(private readonly host: HTMLElement) {
    this.cameraRig = new VirtualCameraRig(this.scene, host);
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
      this.cameraRig.update();
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
      this.cameraRig.renderPreview();
    });
    const manager = new THREE.LoadingManager();
    const loader = new URDFLoader(manager);
    loader.parseCollision = false;
    manager.onError = (url) => console.error("机械臂资源加载失败", url);
    loader.load(`${import.meta.env.BASE_URL}robots/so101/so101_new_calib.urdf`, (robot) => {
      if (this.disposed) { manager.onLoad = () => this.release(robot); return; }
      this.robot = robot;
      this.scene.add(robot);
      manager.onLoad = () => {
        if (this.disposed) { this.release(robot); return; }
        robot.updateMatrixWorld(true);
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
      };
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
    this.targets = { ...positions };
  }

  private updateJoints(dt: number): void {
    if (!this.robot) return;
    for (const [name, target] of Object.entries(this.targets)) {
      const joint = this.robot.joints[name];
      const current = joint.jointValue[0];
      const step = Math.min(0.25, joint.limit.velocity) * dt;
      joint.setJointValue(current + Math.max(-step, Math.min(step, target - current)));
    }
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
      if (!(child instanceof THREE.Mesh)) return;
      child.geometry.dispose();
      (Array.isArray(child.material) ? child.material : [child.material]).forEach((material) => material.dispose());
    });
  }

  dispose(): void {
    this.disposed = true;
    this.motion.dispose();
    this.observer.disconnect();
    this.renderer.setAnimationLoop(null);
    this.controls.dispose();
    this.cameraRig.dispose();
    this.release(this.scene);
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}


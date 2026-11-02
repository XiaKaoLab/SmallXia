/** 功能：等待 URDF 及全部网格加载完成，供独立模型场景复用。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
import URDFLoader, { type URDFRobot } from "urdf-loader";

export class RobotAssetLoader {
  load(url: string): Promise<URDFRobot> {
    return new Promise((resolve, reject) => {
      const loader = new URDFLoader(new THREE.LoadingManager());
      const meshes: Promise<void>[] = [];
      loader.parseCollision = false;
      loader.loadMeshCb = (path, manager, material, done) => {
        meshes.push(new Promise<void>((finish, fail) => {
          loader.defaultMeshLoader(path, manager, material, (mesh, error) => {
            if (error) { fail(error); return; }
            done(mesh); finish();
          });
        }));
      };
      loader.load(url, robot => { void Promise.all(meshes).then(() => resolve(robot), reject); }, undefined, reject);
    });
  }
}

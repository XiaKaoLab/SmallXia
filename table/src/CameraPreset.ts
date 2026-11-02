/** 功能：共享固定腕部相机装配位置，供积木与推理场景复用。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import type { VirtualCameraConfig } from "./VirtualCameraRig";

// 安装板STL坐标转换后的显示外参，与core腕部相机保持一致。
export const SO101_WRIST_CAMERA_PRESET: VirtualCameraConfig = {
  visible: true, parent_link: "gripper_link",
  position: [0.0025, -0.068697378, -0.003110223],
  rotation: [25 * Math.PI / 180, 0, 0], fov: 60,
};

// SO100 官方一体式支架：按 STL 安装板放置光心与镜头朝向。
export const WRIST_CAMERA_PRESET: VirtualCameraConfig = {
  ...SO101_WRIST_CAMERA_PRESET,
  position: [-0.0025, -0.005059929107, -0.068479164259],
  rotation: [-115 * Math.PI / 180, 0, 0],
};

export function wristCameraForModel(model: string, config: VirtualCameraConfig): VirtualCameraConfig {
  const legacy = SO101_WRIST_CAMERA_PRESET;
  if (model !== "so100_mid_calib" || config.parent_link !== "gripper_link"
    || !Array.isArray(config.rotation) || !Array.isArray(config.position)) return config;
  const oldPosition = config.position.every((value, i) => Math.abs(value - legacy.position[i]) < 1e-6);
  const oldRotation = [legacy.rotation, [-65 * Math.PI / 180, 0, 0]].some(rotation =>
    config.rotation.every((value, i) => Math.abs(value - rotation[i]) < 1e-6));
  if (!oldPosition || !oldRotation) return config;
  // 仅迁移已装配的旧固定预设，不覆盖自定义外参。
  return { ...config, position: [...WRIST_CAMERA_PRESET.position], rotation: [...WRIST_CAMERA_PRESET.rotation] };
}

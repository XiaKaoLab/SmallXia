/** 功能：共享固定腕部相机装配位置，供积木与推理场景复用。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import type { VirtualCameraConfig } from "./VirtualCameraRig";

// 安装板STL坐标转换后的显示外参，与core腕部相机保持一致。
export const WRIST_CAMERA_PRESET: VirtualCameraConfig = {
  visible: true, parent_link: "gripper_link",
  position: [0.0025, -0.068697378, -0.003110223],
  rotation: [25 * Math.PI / 180, 0, 0], fov: 60,
};

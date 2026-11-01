/** 功能：定义虚拟相机装配积木并生成调用模型 API 的 Python。
 * Created on 2026-11-01; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";

export const CAMERA_BLOCK_TYPE = "table_mount_camera";
// 安装连杆来自腕部替换支架；光心偏移为固定显示示意，非实测外参。
export const CAMERA_PRESET = {
  visible: true,
  parent_link: "gripper_link",
  position: [0.03, 0, -0.015],
  rotation: [0, 0, 0],
  fov: 60,
} as const;

export function registerCameraBlock(): void {
  Blockly.Blocks[CAMERA_BLOCK_TYPE] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("装配相机");
      this.setColour("#587e9d");
      this.setTooltip("在固定腕部位置装配相机；点击运行后显示相机和画面。");
    },
  };
  pythonGenerator.forBlock[CAMERA_BLOCK_TYPE] = () => {
    const payload = CAMERA_PRESET;
    return `# 功能：通过模型 API 装配虚拟相机。\n# Created on 2026-11-01; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nimport os\nfrom urllib.request import Request, urlopen\n\ncamera = json.loads(${JSON.stringify(JSON.stringify(payload))})\nrequest = Request(\n    "http://127.0.0.1:8766/api/v1/robots/table/camera",\n    data=json.dumps(camera, allow_nan=False).encode("utf-8"),\n    headers={"Content-Type": "application/json",\n             "Authorization": "Bearer " + os.environ["XIAOXIA_MOTION_TOKEN"]},\n    method="POST",\n)\nwith urlopen(request, timeout=1) as response:\n    print(json.loads(response.read()))\n`;
  };
}

/** 功能：定义虚拟相机装配积木并生成调用模型 API 的 Python。
 * Created on 2026-11-01; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { WRIST_CAMERA_PRESET as CAMERA_PRESET } from "../CameraPreset";

export const CAMERA_BLOCK_TYPE = "table_mount_camera";
// STL 安装板：CAD 法向 (0, -sin25°, cos25°)，平面距原点 -33.261 mm。
// 板中心沿板长轴 63.779 mm；光心在板外 8 mm，经 URDF visual 原点转换。
// 固定于真实支架板，镜头高度为显示近似，非实测标定外参。
export { WRIST_CAMERA_PRESET as CAMERA_PRESET } from "../CameraPreset";

export function registerCameraBlock(): void {
  Blockly.Blocks[CAMERA_BLOCK_TYPE] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("装配相机");
      this.setPreviousStatement(true); this.setNextStatement(true);
      this.setColour("#587e9d");
      this.setTooltip("装配并显示腕部相机。");
    },
  };
  pythonGenerator.forBlock[CAMERA_BLOCK_TYPE] = () => {
    const payload = CAMERA_PRESET;
    return `# 功能：通过模型 API 装配虚拟相机。\n# Created on 2026-11-01; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nimport os\nfrom urllib.request import Request, urlopen\n\ncamera = json.loads(${JSON.stringify(JSON.stringify(payload))})\nrequest = Request(\n    "http://127.0.0.1:8766/api/v1/robots/table/camera",\n    data=json.dumps(camera, allow_nan=False).encode("utf-8"),\n    headers={"Content-Type": "application/json",\n             "Authorization": "Bearer " + os.environ["XIAOXIA_MOTION_TOKEN"]},\n    method="POST",\n)\nwith urlopen(request, timeout=1) as response:\n    print(json.loads(response.read()))\n`;
  };
}

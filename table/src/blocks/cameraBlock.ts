/** 功能：定义虚拟相机装配积木并生成调用模型 API 的 Python。
 * Created on 2026-11-01; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";

export const CAMERA_BLOCK_TYPE = "table_mount_camera";
export const CAMERA_LINKS = [
  ["夹爪座", "gripper_link"], ["腕部", "wrist_link"], ["下臂", "lower_arm_link"],
  ["上臂", "upper_arm_link"], ["肩部", "shoulder_link"], ["底座", "base_link"],
  ["夹爪末端", "gripper_frame_link"],
] as const;
export const CAMERA_NUMBERS: Record<string, { label: string; lower: number; upper: number; initial: number; unit: string }> = {
  x: { label: "位置 X", lower: -2, upper: 2, initial: 0.03, unit: "m" },
  y: { label: "位置 Y", lower: -2, upper: 2, initial: 0, unit: "m" },
  z: { label: "位置 Z", lower: -2, upper: 2, initial: -0.015, unit: "m" },
  roll: { label: "翻滚", lower: -Math.PI, upper: Math.PI, initial: 0, unit: "rad" },
  pitch: { label: "俯仰", lower: -Math.PI, upper: Math.PI, initial: 0, unit: "rad" },
  yaw: { label: "偏航", lower: -Math.PI, upper: Math.PI, initial: 0, unit: "rad" },
  fov: { label: "视场角", lower: 10, upper: 140, initial: 60, unit: "°" },
};

export function registerCameraBlock(): void {
  Blockly.Blocks[CAMERA_BLOCK_TYPE] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("装配虚拟相机");
      this.appendDummyInput().appendField("安装到")
        .appendField(new Blockly.FieldDropdown(CAMERA_LINKS.map(([label, value]) => [label, value])), "parent_link");
      this.appendDummyInput().appendField("相机及画面")
        .appendField(new Blockly.FieldDropdown([["不显示", "hidden"], ["显示", "shown"]]), "display");
      for (const [name, spec] of Object.entries(CAMERA_NUMBERS)) {
        this.appendDummyInput().appendField(spec.label)
          .appendField(new Blockly.FieldNumber(spec.initial, spec.lower, spec.upper), name).appendField(spec.unit);
      }
      this.setColour("#587e9d");
      this.setTooltip("在所选连杆局部坐标中装配虚拟相机；文档位置是 Wrist Roll 替换支架(gripper_link)，偏移为示意值；镜头朝局部 -Z，姿态为 Rz(yaw)Ry(pitch)Rx(roll)。");
    },
  };
  pythonGenerator.forBlock[CAMERA_BLOCK_TYPE] = (block) => {
    const parent = String(block.getFieldValue("parent_link"));
    if (!CAMERA_LINKS.some(([, value]) => value === parent)) throw new Error("无效安装连杆");
    const fields = Object.fromEntries(Object.entries(CAMERA_NUMBERS).map(([name, spec]) => {
      const value = Number(block.getFieldValue(name));
      if (!Number.isFinite(value) || value < spec.lower || value > spec.upper) throw new Error(`${name} 相机参数越界`);
      return [name, value];
    }));
    const payload = { visible: block.getFieldValue("display") === "shown", parent_link: parent, position: [fields.x, fields.y, fields.z],
      rotation: [fields.roll, fields.pitch, fields.yaw], fov: fields.fov };
    return `# 功能：通过模型 API 装配虚拟相机。\n# Created on 2026-11-01; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nimport os\nfrom urllib.request import Request, urlopen\n\ncamera = json.loads(${JSON.stringify(JSON.stringify(payload))})\nrequest = Request(\n    "http://127.0.0.1:8766/api/v1/robots/table/camera",\n    data=json.dumps(camera, allow_nan=False).encode("utf-8"),\n    headers={"Content-Type": "application/json",\n             "Authorization": "Bearer " + os.environ["XIAOXIA_MOTION_TOKEN"]},\n    method="POST",\n)\nwith urlopen(request, timeout=1) as response:\n    print(json.loads(response.read()))\n`;
  };
}

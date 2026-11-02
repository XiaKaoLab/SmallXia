/** 功能：定义唯一机械臂位置积木并生成调用模型 API 的 Python。
 * Created on 2026-11-01; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { JointAngleSlider } from "./JointAngleSlider";
import { jointPreview } from "../JointPreview";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";

export const JOINTS = [
  ["shoulder_pan", "肩部旋转"], ["shoulder_lift", "肩部抬升"],
  ["elbow_flex", "肘部弯曲"], ["wrist_flex", "腕部弯曲"],
  ["wrist_roll", "腕部旋转"], ["gripper", "夹爪"],
] as const;
export type Limits = Record<string, { lower: number; upper: number }>;
export const BLOCK_TYPE = "table_set_arm_position";

export function registerPositionBlock(limits: Limits, onSlide: (block: Blockly.Block) => void): void {
  Blockly.Blocks[BLOCK_TYPE] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("机械臂（")
        .appendField(new Blockly.FieldDropdown(function () { return armTargetCatalog.options(this.getValue()); }), "TARGET")
        .appendField("）");
      for (const [index, [name, label]] of JOINTS.entries()) {
        const { lower, upper } = limits[name];
        this.appendDummyInput().appendField(`M${index + 1} ${label}`)
          .appendField(new JointAngleSlider(Math.max(lower, Math.min(0, upper)), lower, upper, `M${index + 1} ${label}`, (angle) => {
            if (this.isInFlyout) return angle;
            if (this.getFieldValue("TARGET") !== "simulation") return angle;
            const accepted = jointPreview.stage(name, angle);
            this.setFieldValue(String(accepted), name);
            onSlide(this);
            return accepted;
          }), name);
      }
      this.setColour("#638b80");
      this.setTooltip("选择机械臂，拖动滑杆设置角度。");
      this.setPreviousStatement(true); this.setNextStatement(true);
    },
  };
  pythonGenerator.forBlock[BLOCK_TYPE] = (block) => {
    const target = String(block.getFieldValue("TARGET") ?? "simulation");
    if (target !== "simulation") return `# 功能：检查机械臂目标绑定。\n# Created on 2026-11-02; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nraise RuntimeError(${JSON.stringify(`${target.replace(/^serial:/, "")} 未连接控制服务`)})\n`;
    const positions = JOINTS.map(([name]) => {
      const value = Number(block.getFieldValue(name));
      if (!Number.isFinite(value) || value < limits[name].lower || value > limits[name].upper) {
        throw new Error(`${name} 超出模型限位`);
      }
      return `    "${name}": ${value},`;
    }).join("\n");
    return `# 功能：通过本机 API 设置 table 模型六轴目标。\n# Created on 2026-11-01; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nimport os\nimport time\nimport uuid\nfrom urllib.request import Request, urlopen\n\njoint_positions = {\n${positions}\n}\n\nrequest = Request(\n    "http://127.0.0.1:8766/api/v1/robots/table/motions",\n    data=json.dumps({\n        "request_id": str(uuid.uuid4()),\n        "expires_at_ms": int(time.time() * 1000) + 200,\n        "unit": "rad",\n        "joint_positions": joint_positions,\n    }, allow_nan=False).encode("utf-8"),\n    headers={\n        "Content-Type": "application/json",\n        "Authorization": "Bearer " + os.environ["XIAOXIA_MOTION_TOKEN"],\n    },\n    method="POST",\n)\n# 不自动重试：超时后先查询模型状态。\nwith urlopen(request, timeout=1) as response:\n    print(json.dumps(json.loads(response.read()), ensure_ascii=False))\n`;
  };
}

export function parseModelLimits(urdf: string): Limits {
  const xml = new DOMParser().parseFromString(urdf, "application/xml");
  const limits: Limits = {};
  for (const [name] of JOINTS) {
    const joint = Array.from(xml.documentElement.children).find((node) => node.tagName === "joint" && node.getAttribute("name") === name);
    const limit = joint?.querySelector("limit");
    const lowerText = limit?.getAttribute("lower");
    const upperText = limit?.getAttribute("upper");
    const lower = lowerText ? Number(lowerText) : NaN;
    const upper = upperText ? Number(upperText) : NaN;
    if (!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper) throw new Error(`无法读取 ${name} 模型限位`);
    limits[name] = { lower, upper };
  }
  return limits;
}

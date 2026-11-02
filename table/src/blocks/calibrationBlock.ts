/** 功能：生成只读机械臂显示对齐积木，记录当前仿真姿态和六轴方向。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";
import { JOINTS } from "./positionBlock";
import { jointPreview } from "../JointPreview";

export const CALIBRATION_BLOCK = "table_calibrate_arm";
export function registerCalibrationBlock(): void {
  Blockly.Blocks[CALIBRATION_BLOCK] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("校准机械臂")
        .appendField(new Blockly.FieldDropdown(function () {
          const options = armTargetCatalog.options(this.getValue()).filter(([, value]) => value !== "simulation");
          return options.length ? options : [["未发现串口", "unavailable"]];
        }), "TARGET");
      for (const [index, [name, label]] of JOINTS.entries()) {
        this.appendDummyInput().appendField(`M${index + 1} ${label}方向`)
          .appendField(new Blockly.FieldDropdown([["正向", "1"], ["反向", "-1"]]), name);
      }
      this.appendDummyInput().appendField("先将实机摆成当前仿真姿态");
      this.appendDummyInput().appendField("只读显示对齐，不改写电机");
      this.setColour("#638b80"); this.setPreviousStatement(true); this.setNextStatement(true);
      this.setTooltip("手动将实机摆成仿真当前姿态，再运行记录参考位置。跟随时显示相对角度；方向不符可改为反向并重新对齐。不能作为实机运动校准。");
    },
  };
  pythonGenerator.forBlock[CALIBRATION_BLOCK] = block => {
    const target = String(block.getFieldValue("TARGET"));
    if (!/^serial:COM[1-9][0-9]*$/.test(target)) throw new Error("校准机械臂请选择实际 COM 口");
    const reference = Object.fromEntries(JOINTS.map(([name]) => [name, jointPreview.displayed[name]]));
    if (JOINTS.some(([name]) => !Number.isFinite(reference[name]))) throw new Error("等待仿真模型加载后再运行校准");
    const directions = Object.fromEntries(JOINTS.map(([name]) => [name, Number(block.getFieldValue(name))]));
    return `# 功能：启动只读机械臂显示对齐。\n# Created on 2026-11-02; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nfrom xiaoxia_core.communication.display_alignment import DisplayAlignment\nprint(json.dumps({"display_alignment": DisplayAlignment.start(${JSON.stringify(target.slice(7))}, ${JSON.stringify(reference)}, ${JSON.stringify(directions)})}, ensure_ascii=False))\n`;
  };
}

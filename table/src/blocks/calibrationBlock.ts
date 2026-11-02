/** 功能：生成只读机械臂显示对齐积木，记录明确填写的参考角度和六轴方向。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";
import { JOINTS } from "./positionBlock";

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
        this.appendDummyInput().appendField(`M${index + 1} ${label}`)
          .appendField(new Blockly.FieldNumber(0, undefined, undefined, 0.1), `${name}_ANGLE`)
          .appendField("° 方向")
          .appendField(new Blockly.FieldDropdown([["正向", "1"], ["反向", "-1"]]), name);
      }
      this.appendDummyInput().appendField("填写实机当前已知角度后运行");
      this.appendDummyInput().appendField("只读显示对齐，不改写电机");
      this.setColour("#638b80"); this.setPreviousStatement(true); this.setNextStatement(true);
      this.setTooltip("手动将实机摆成已知姿态，再填写参考角度。填写各轴在 URDF 坐标中的已知参考角度，记录固定零点；不能从编码器直接确定物理零点。不能作为实机运动校准。");
    },
  };
  pythonGenerator.forBlock[CALIBRATION_BLOCK] = block => {
    const target = String(block.getFieldValue("TARGET"));
    if (!/^serial:COM[1-9][0-9]*$/.test(target)) throw new Error("校准机械臂请选择实际 COM 口");
    const reference = Object.fromEntries(JOINTS.map(([name]) => [name, Number(block.getFieldValue(`${name}_ANGLE`)) * Math.PI / 180]));
    if (JOINTS.some(([name]) => !Number.isFinite(reference[name]))) throw new Error("请填写完整的六轴参考角度");
    const directions = Object.fromEntries(JOINTS.map(([name]) => [name, Number(block.getFieldValue(name))]));
    return `# 功能：启动只读机械臂显示对齐。\n# Created on 2026-11-02; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nfrom xiaoxia_core.communication.display_alignment import DisplayAlignment\nprint(json.dumps({"display_alignment": DisplayAlignment.start(${JSON.stringify(target.slice(7))}, ${JSON.stringify(reference)}, ${JSON.stringify(directions)})}, ensure_ascii=False))\n`;
  };
}

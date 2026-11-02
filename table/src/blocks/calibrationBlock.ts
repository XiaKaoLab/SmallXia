/** 功能：生成机械臂官方校准积木，复用官方校准，缺失时同时采集六轴最小和最大位置。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";

export const CALIBRATION_BLOCK = "table_calibrate_arm";
export function registerCalibrationBlock(): void {
  Blockly.Blocks[CALIBRATION_BLOCK] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("校准机械臂")
        .appendField(new Blockly.FieldDropdown(function () {
          const options = armTargetCatalog.options(this.getValue()).filter(([, value]) => value !== "simulation");
          return options.length ? options : [["未发现串口", "unavailable"]];
        }), "TARGET");
      this.appendDummyInput().appendField(new Blockly.FieldDropdown([["已有校准自动复用", "reuse"], ["重新校准", "recalibrate"]]), "MODE");
      this.setColour("#638b80"); this.setPreviousStatement(true); this.setNextStatement(true);
      this.setTooltip("转动各关节，采集范围后保存。");
    },
  };
  pythonGenerator.forBlock[CALIBRATION_BLOCK] = block => {
    const target = String(block.getFieldValue("TARGET"));
    if (!/^serial:COM[1-9][0-9]*$/.test(target)) throw new Error("请选择 COM 口");
    return `# 功能：检查并复用官方机械臂校准。\n# Created on 2026-11-02; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nfrom xiaoxia_core.communication.display_alignment import DisplayAlignment\nprint(json.dumps({"display_alignment": DisplayAlignment.start(${JSON.stringify(target.slice(7))}, recalibrate=${block.getFieldValue("MODE") === "recalibrate" ? "True" : "False"})}, ensure_ascii=False))\n`;
  };
}

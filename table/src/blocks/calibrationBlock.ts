/** 功能：生成机械臂官方校准积木，复用官方校准，缺失时逐轴采集最小和最大位置。
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
      this.appendDummyInput().appendField("已有校准自动复用");
      this.appendDummyInput().appendField("缺失时逐轴检查最小和最大位置");
      this.setColour("#638b80"); this.setPreviousStatement(true); this.setNextStatement(true);
      this.setTooltip("读取并核对设备官方校准。有效时直接复用；缺失时在面板引导记录中位和逐轴极限，完成后保存。手动移动关节，不自动驱动电机。");
    },
  };
  pythonGenerator.forBlock[CALIBRATION_BLOCK] = block => {
    const target = String(block.getFieldValue("TARGET"));
    if (!/^serial:COM[1-9][0-9]*$/.test(target)) throw new Error("校准机械臂请选择实际 COM 口");
    return `# 功能：检查并复用官方机械臂校准。\n# Created on 2026-11-02; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nfrom xiaoxia_core.communication.display_alignment import DisplayAlignment\nprint(json.dumps({"display_alignment": DisplayAlignment.start(${JSON.stringify(target.slice(7))})}, ensure_ascii=False))\n`;
  };
}

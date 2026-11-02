/** 功能：复用官方行程校准与模型坐标转换，将实机关节反馈映射到 table 仿真模型。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";
import { CALIBRATION_BLOCK } from "./calibrationBlock";

export const ARM_MAPPING_BLOCK = "table_map_hardware_arm";
export function registerArmMappingBlock(): void {
  Blockly.Blocks[ARM_MAPPING_BLOCK] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("映射真机到仿真")
        .appendField(new Blockly.FieldDropdown(function () {
          const ports = armTargetCatalog.options(this.getValue()).filter(([, value]) => value !== "simulation");
          return ports.length ? ports : [["未发现串口", "unavailable"]];
        }), "TARGET");
      this.appendDummyInput().appendField("复用官方校准 · 缺失则引导检查");
      this.setPreviousStatement(true); this.setNextStatement(true); this.setColour("#638b80");
      this.setTooltip("自动复用匹配的官方校准；缺失时引导同时检查六轴最小和最大位置。运行本积木只读实机编码器，按官方单位转换计算关节角度并发送到仿真模型；已有有效校准时不改写参数、不使能力矩。面板可停止映射。");
    },
  };
  pythonGenerator.forBlock[ARM_MAPPING_BLOCK] = block => {
    const target = String(block.getFieldValue("TARGET"));
    if (!/^serial:COM[1-9][0-9]*$/.test(target)) throw new Error("映射真机请选择实际 COM 口");
    if (block.workspace.getBlocksByType(CALIBRATION_BLOCK, false).some(item => item.isEnabled())) {
      throw new Error("请先单独运行校准机械臂，完成后禁用或移除校准积木，再运行真机映射");
    }
    return `# 功能：只读实机反馈并映射到仿真模型。\n# Created on 2026-11-02; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nfrom xiaoxia_core.communication.display_alignment import DisplayAlignment\nprint(json.dumps({"display_alignment": DisplayAlignment.start_mapping(${JSON.stringify(target.slice(7))})}, ensure_ascii=False))\n`;
  };
}

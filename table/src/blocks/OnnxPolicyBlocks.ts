/** 功能：提供已有抓球模型的 ONNX 导出和 Runtime 仿真推理积木。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { onnxModelCatalog } from "./OnnxModelCatalog";

export const ONNX_EXPORT = "table_policy_onnx_export";
export const ONNX_RUN = "table_policy_onnx_run";
export const ONNX_TYPES = [ONNX_EXPORT, ONNX_RUN];

export class OnnxPolicyBlocks {
  register(): void {
    for (const type of ONNX_TYPES) {
      Blockly.Blocks[type] = {
        init(this: Blockly.Block) {
          this.appendDummyInput().appendField(type === ONNX_EXPORT ? "导出抓球模型 ONNX" : "ONNX 推理 · 拿取小球");
          this.appendDummyInput().appendField("模型").appendField(new Blockly.FieldDropdown(function () {
            return onnxModelCatalog.options(type === ONNX_RUN, this.getValue());
          }), "MODEL_ID");
          if (type === ONNX_RUN) this.appendDummyInput().appendField("运行")
            .appendField(new Blockly.FieldNumber(1, 1, 1000, 1), "ROUNDS").appendField("轮");
          this.setPreviousStatement(true); this.setNextStatement(true); this.setColour("#7d7297");
          this.setTooltip(type === ONNX_EXPORT ? "导出训练模型。"
            : "使用模型进行仿真推理。");
        },
      };
      pythonGenerator.forBlock[type] = block => {
        const client = "__import__('xiaoxia_core.reinforcement.client', fromlist=['ReinforcementClient']).ReinforcementClient()";
        const id = JSON.stringify(block.getFieldValue("MODEL_ID"));
        const call = type === ONNX_EXPORT ? `${client}.export_onnx(${id})` : `${client}.rollout_onnx(${id}, rounds=${block.getFieldValue("ROUNDS")})`;
        return `print(__import__('json').dumps({${JSON.stringify(type === ONNX_EXPORT ? "onnx_export" : "ball_training")}: ${call}}))\n`;
      };
    }
  }
}

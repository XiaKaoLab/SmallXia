/** 功能：通用文字识别和按文字抓取方块积木，目标使用任意文本输入。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";
import { cameraCatalog } from "./CameraCatalog";
import { onnxModelCatalog } from "./OnnxModelCatalog";
export const TEXT_READ="table_text_read";
export const TEXT_PICK="table_text_pick";
export const TEXT_VISION_TYPES=[TEXT_READ,TEXT_PICK];
export class TextVisionBlocks {
  register(): void {
    Blockly.Blocks[TEXT_READ]={init(this:Blockly.Block) {
      this.appendDummyInput().appendField("识别文字").appendField(new Blockly.FieldDropdown(function(){return cameraCatalog.options(this.getValue());}),"CAMERA_ID");
      this.setOutput(true);this.setColour("#587e9d");this.setTooltip("读取相机文字，返回文字框、置信度和来源。");
    }};
    Blockly.Blocks[TEXT_PICK]={init(this:Blockly.Block) {
      this.appendDummyInput().appendField("仿真抓取文字方块").appendField(new Blockly.FieldTextInput("A"),"TARGET_TEXT");
      this.appendDummyInput().appendField("抓取模型").appendField(new Blockly.FieldDropdown(function(){return onnxModelCatalog.options(true,this.getValue());}),"MODEL_ID");
      this.appendDummyInput().appendField("运行").appendField(new Blockly.FieldNumber(1,1,100,1),"ROUNDS").appendField("轮");
      this.setPreviousStatement(true);this.setNextStatement(true);this.setColour("#7d7297");
      this.setTooltip("先OCR识别和定位，再复用抓取模型。仿真自动生成含目标的三个方块。");
    }};
    const http="__import__('xiaoxia_core.blocks.workflow', fromlist=['BlockWorkflow']).BlockWorkflow.http";
    pythonGenerator.forBlock[TEXT_READ]=block=>[`${http}('vision/text-recognitions', {'camera_id':${JSON.stringify(block.getFieldValue("CAMERA_ID"))}})`,Order.FUNCTION_CALL];
    pythonGenerator.forBlock[TEXT_PICK]=block=>`_text_job = ${http}('vision/text-picks', {'target_text':${JSON.stringify(block.getFieldValue("TARGET_TEXT"))}, 'model_job_id':${JSON.stringify(block.getFieldValue("MODEL_ID"))}, 'rounds':${block.getFieldValue("ROUNDS")}})\nprint(__import__('json').dumps({'ball_training':_text_job}), flush=True)\n__import__('xiaoxia_core.blocks.workflow', fromlist=['BlockWorkflow']).BlockWorkflow().wait_job(_text_job, 'reinforcement')\n`;
  }
}

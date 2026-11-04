/** 功能：提供积木启动的六轴坐标映射向导入口。
 * Created on 2026-11-04; Updated on 2026-11-04
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";
export const COORDINATE_BLOCK="table_calibrate_mapping";
export function registerCoordinateBlock():void {
  Blockly.Blocks[COORDINATE_BLOCK]={init(this:Blockly.Block){
    this.appendDummyInput().appendField("校准关节映射").appendField(new Blockly.FieldDropdown(function(){
      const options=armTargetCatalog.options(this.getValue()==="unavailable"||!this.getValue()?"serial:COM17":this.getValue()).filter(([,v])=>v!=="simulation");
      return options.length?options:[["未发现串口","unavailable"]];
    }),"TARGET");
    this.setPreviousStatement(false);this.setNextStatement(false);this.setColour("#638b80");
    this.setTooltip("运行后按模型提示确认六轴零点和方向，一次保存。");
  }};
  pythonGenerator.forBlock[COORDINATE_BLOCK]=block=>{
    const target=String(block.getFieldValue("TARGET"));
    if(!/^serial:COM[1-9][0-9]*$/.test(target))throw new Error("请选择 COM 口");
    return `import json\nfrom xiaoxia_core.blocks.workflow import BlockWorkflow\nprint(json.dumps({"coordinate_calibration": BlockWorkflow.http("sim2real/calibrations", {"port":${JSON.stringify(target.slice(7))},"profile":"so100.local.yaml"})},ensure_ascii=False))\n`;
  };
}

/** 功能：复用策略目标和真实相机选择，默认保持仿真执行。
 * Created on 2026-11-05; Updated on 2026-11-05
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { armTargetCatalog } from "./ArmTargetCatalog";
import { cameraCatalog } from "./CameraCatalog";

export class PolicyTargetFields {
  static append(block:Blockly.Block):void {
    block.appendDummyInput().appendField("目标").appendField(new Blockly.FieldDropdown(function(){
      return armTargetCatalog.options(this.getValue());
    }),"TARGET");
    block.appendDummyInput("POLICY_CAMERA").appendField("真实相机").appendField(new Blockly.FieldDropdown(function(){
      return [["默认真实相机","real"],...cameraCatalog.realOptions(this.getValue()).filter(([,id])=>id.startsWith("opencv_"))];
    }),"POLICY_CAMERA");
    block.getInput("POLICY_CAMERA")!.setVisible(false);
    block.setOnChange(()=>{
      const input=block.getInput("POLICY_CAMERA");
      const visible=String(block.getFieldValue("TARGET")).startsWith("serial:");
      if(input&&input.isVisible()!==visible)input.setVisible(visible);
    });
    block.setTooltip("仿真或真机运行示教策略；真机先接使能积木，结束后接失能积木。");
  }
  static arguments(block:Blockly.Block):string {
    return `target=${JSON.stringify(block.getFieldValue("TARGET")||"simulation")}, camera_source=${JSON.stringify(block.getFieldValue("POLICY_CAMERA")||"real")}`;
  }
}

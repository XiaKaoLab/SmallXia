/** 功能：红色物体跟随积木，复用相机和机械臂目标目录。
 * Created on 2026-11-05; Updated on 2026-11-05
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";
import { cameraCatalog } from "./CameraCatalog";

export const RED_TRACK="table_track_red_object";
export class RedTrackingBlocks {
  static register():void {
    Blockly.Blocks[RED_TRACK]={init(this:Blockly.Block){
      this.appendDummyInput().appendField("跟踪红色物体");
      this.appendDummyInput().appendField("目标").appendField(new Blockly.FieldDropdown(function(){return armTargetCatalog.options(this.getValue());}),"TARGET");
      this.appendDummyInput().appendField("相机").appendField(new Blockly.FieldDropdown(function(){return cameraCatalog.options(this.getValue());}),"SOURCE");
      this.appendDummyInput().appendField("时长").appendField(new Blockly.FieldNumber(0,0,3600,1),"SECONDS").appendField("秒 · 0 为持续");
      this.appendDummyInput().appendField("水平反向").appendField(new Blockly.FieldCheckbox("FALSE"),"FLIP_X")
        .appendField("垂直反向").appendField(new Blockly.FieldCheckbox("FALSE"),"FLIP_Y");
      this.setPreviousStatement(true);this.setNextStatement(true);this.setColour("#587e9d");
      this.setTooltip("相机须随机械臂运动。以肩部旋转和腕部弯曲对准红色目标；真机先使能。丢失时停止调整，点击停止结束跟随。");
    }};
    pythonGenerator.forBlock[RED_TRACK]=block=>{
      const camera=String(block.getFieldValue("SOURCE"));
      if(camera==="unavailable")throw new Error("请选择相机");
      return `__import__('xiaoxia_core.blocks.red_tracking', fromlist=['RedObjectTracker']).RedObjectTracker().run(target=${JSON.stringify(block.getFieldValue("TARGET"))}, camera=${JSON.stringify(camera)}, seconds=${Number(block.getFieldValue("SECONDS"))}, horizontal=${block.getFieldValue("FLIP_X")==="TRUE"?-1:1}, vertical=${block.getFieldValue("FLIP_Y")==="TRUE"?1:-1})\n`;
    };
  }
}

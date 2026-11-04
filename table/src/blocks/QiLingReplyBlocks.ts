/** 功能：器灵完整回复、等待与文本条件积木，供分支和循环组合。
 * Created on 2026-11-04; Updated on 2026-11-04
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";

export const QILING_WAIT="table_qiling_wait";
export const QILING_REPLY="table_qiling_reply";
export const TEXT_MATCH="table_text_match";
export const QILING_REPLY_TYPES=[QILING_WAIT,QILING_REPLY,TEXT_MATCH];

export class QiLingReplyBlocks {
  private static spirit():Blockly.FieldDropdown {
    return new Blockly.FieldDropdown(function(){
      const workspace=this.getSourceBlock()?.workspace;
      const names=[...new Set(["器灵",...(workspace?.getBlocksByType("table_qiling_load",false)??[])
        .map(block=>String(block.getFieldValue("SPIRIT")).trim()).filter(Boolean),this.getValue()].filter(Boolean))];
      return names.map(name=>[name,name] as [string,string]);
    });
  }
  static register():void {
    Blockly.Blocks[QILING_WAIT]={init(this:Blockly.Block){
      this.appendDummyInput().appendField("等待").appendField(QiLingReplyBlocks.spirit(),"SPIRIT").appendField("回复");
      this.setPreviousStatement(true);this.setNextStatement(true);this.setColour("#5d758e");
      this.setTooltip("放在发送消息后，确认器灵已完整回复，再继续执行。");
    }};
    Blockly.Blocks[QILING_REPLY]={init(this:Blockly.Block){
      this.appendDummyInput().appendField(QiLingReplyBlocks.spirit(),"SPIRIT").appendField("回复内容");
      this.setOutput(true,"String");this.setColour("#5d758e");
      this.setTooltip("本次运行中，器灵最近一次完整回复。尚未回复时为空文本。");
    }};
    Blockly.Blocks[TEXT_MATCH]={init(this:Blockly.Block){
      this.appendValueInput("TEXT").setCheck("String").appendField("文本");
      this.appendValueInput("VALUE").setCheck("String").appendField(new Blockly.FieldDropdown([["等于","EQUAL"],["包含","CONTAINS"]]),"OP");
      this.setInputsInline(true);this.setOutput(true,"Boolean");this.setColour("#687f9b");
      this.setTooltip("区分大小写，按原文判断。可放进如果或循环条件。");
    }};
    const client="__import__('xiaoxia_core.blocks.qiling', fromlist=['QiLingBlock']).QiLingBlock()";
    pythonGenerator.forBlock[QILING_WAIT]=block=>`${client}.wait_reply(name=${JSON.stringify(block.getFieldValue("SPIRIT"))})\n`;
    pythonGenerator.forBlock[QILING_REPLY]=block=>[`${client}.reply(name=${JSON.stringify(block.getFieldValue("SPIRIT"))})`,Order.FUNCTION_CALL];
    pythonGenerator.forBlock[TEXT_MATCH]=(block,generator)=>{
      const text=generator.valueToCode(block,"TEXT",Order.NONE)||"''";
      const value=generator.valueToCode(block,"VALUE",Order.NONE)||"''";
      const expression=block.getFieldValue("OP")==="CONTAINS"?`(${value}) in (${text})`:`(${text}) == (${value})`;
      return [expression,Order.RELATIONAL];
    };
  }
}

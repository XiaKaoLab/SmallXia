/** 功能：器灵分类与独立 Agent 积木，模型和消息均在积木内配置，回复原位显示。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";
import { agentClient } from "../chat/AgentClient";
import { agentCursor } from "../interaction/AgentCursor";
import { ToolPresentation } from "../chat/ToolPresentation";
export const QILING_AGENT="table_qiling_agent";
export interface QiLingReceipt { type: string; node_id: string; delta?: string; name?: string; call_id?: string; failed?: boolean; text?: string; result?: { text: string; model: string } }

class QiLingCatalog {
  private models: string[]=[];
  private defaultModel="";
  private pending=false;
  private workspace?: Blockly.WorkspaceSvg;
  options(selected?: string|null): [string,string][] {
    const options: [string,string][]=[[this.defaultModel?`默认 · ${this.defaultModel}`:"默认模型","default"],...this.models.map(x=>[x,x] as [string,string])];
    if(selected&&!options.some(([,value])=>value===selected))options.push([selected,selected]);
    return options;
  }
  async refresh(): Promise<void> {
    if(this.pending||!agentClient.desktop)return;
    this.pending=true;
    try {
      const result=await agentClient.request<{models:string[];default_model:string}>({action:"qiling_models"});
      this.models=result.models;this.defaultModel=result.default_model;
      const workspace=this.workspace;if(!workspace||workspace.isDragging())return;
      for(const block of [...workspace.getAllBlocks(false),...(workspace.getFlyout()?.getWorkspace().getAllBlocks(false)??[])]) {
        if(block.type!==QILING_AGENT)continue;
        const field=block.getField("MODEL") as Blockly.FieldDropdown;
        const value=field.getValue();field.setOptions(()=>this.options(field.getValue()));field.setValue(value);field.forceRerender();
      }
    } finally {this.pending=false;}
  }
  attach(workspace:Blockly.WorkspaceSvg):()=>void {
    this.workspace=workspace;
    workspace.registerButtonCallback("REFRESH_QILING_MODELS",()=>{void this.refresh().catch(()=>undefined);});
    void this.refresh().catch(()=>undefined);
    return()=>{if(this.workspace===workspace)this.workspace=undefined;};
  }
}
export const qiLingCatalog=new QiLingCatalog();
export class QiLingBlocks {
  private readonly replies=new Map<string,string>();
  private readonly calls=new Set<string>();
  finish():void {for(const id of this.calls)agentCursor.hide(`tool:${id}`);this.calls.clear();}
  register():void {
    Blockly.Blocks[QILING_AGENT]={init(this:Blockly.Block) {
      this.appendDummyInput().appendField("器灵").appendField("模型").appendField(new Blockly.FieldDropdown(function(){return qiLingCatalog.options(this.getValue());}),"MODEL");
      this.appendValueInput("MESSAGE").setCheck("String").appendField("消息");
      this.appendDummyInput().appendField("回复").appendField(new Blockly.FieldLabelSerializable("等待运行"),"REPLY");
      this.setInputsInline(false);this.setPreviousStatement(true);this.setNextStatement(true);this.setColour("#5d758e");
      this.setTooltip("独立机械臂 Agent，仅开放机械臂 MCP。运行时发送消息，并将回复显示在这里。");
    }};
    pythonGenerator.forBlock[QILING_AGENT]=(block,generator)=>{
      const message=generator.valueToCode(block,"MESSAGE",Order.NONE)||"''";
      return `__import__('xiaoxia_core.blocks.qiling', fromlist=['QiLingBlock']).QiLingBlock().run(node_id=${JSON.stringify(block.id)}, message=${message}, model=${JSON.stringify(block.getFieldValue("MODEL"))})\n`;
    };
  }
  receive(workspace:Blockly.WorkspaceSvg|undefined,event:QiLingReceipt):void {
    if(event.type==="tool_started"&&event.call_id){this.calls.add(event.call_id);agentCursor.toolStarted(event.call_id,event.name??"");}
    if(event.type==="tool_completed"&&event.call_id){this.calls.delete(event.call_id);agentCursor.finish(`tool:${event.call_id}`,event.failed);}
    if(event.type==="completed"||event.type==="error")this.finish();
    const block=workspace?.getBlockById(event.node_id);if(!block||block.type!==QILING_AGENT)return;
    let text=this.replies.get(event.node_id)??"";
    if(event.type==="started"){text="";this.replies.set(event.node_id,"");}
    if(event.type==="delta"){text+=event.delta??"";this.replies.set(event.node_id,text);}
    if(event.type==="completed"){text=event.result?.text??text;this.replies.set(event.node_id,text);}
    const display=event.type==="error"?(event.text??"本轮未完成"):event.type==="tool_started"?ToolPresentation.describe(event.name??"")[0]:text||"处理中…";
    Blockly.Events.disable();
    try {block.setFieldValue(display.replace(/\s+/g," ").slice(0,28)+(display.length>28?"…":""),"REPLY");block.setTooltip(display);}
    finally {Blockly.Events.enable();}
  }
}

/** 功能：器灵载入与发送消息积木，绑定模型、共享会话并转发机械臂气泡事件。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";
import { agentClient } from "../chat/AgentClient";
import { agentCursor } from "../interaction/AgentCursor";
import { ToolPresentation } from "../chat/ToolPresentation";
export const QILING_AGENT="table_qiling_agent";
export const QILING_LOAD="table_qiling_load";
export const QILING_SEND="table_qiling_send";
export const QILING_TYPES=[QILING_AGENT,QILING_LOAD,QILING_SEND];
export interface QiLingReceipt { type: string; node_id: string; spirit?: string; target?: string; agent_id?: string; delta?: string; name?: string; call_id?: string; failed?: boolean; text?: string; result?: { text: string; model: string } }

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
        if(![QILING_AGENT,QILING_LOAD].includes(block.type))continue;
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
  private readonly speaking=new Map<string,QiLingReceipt>();
  finish():void {
    for(const id of this.calls)agentCursor.hide(`tool:${id}`);this.calls.clear();
    for(const event of this.speaking.values())window.dispatchEvent(new CustomEvent("table:qiling-speech",{detail:{...event,type:"stopped"}}));
    this.speaking.clear();
  }
  register():void {
    Blockly.Blocks[QILING_LOAD]={init(this:Blockly.Block) {
      this.appendDummyInput().appendField("向").appendField(new Blockly.FieldDropdown([["机械臂","simulation"]]),"TARGET")
        .appendField("载入").appendField(new Blockly.FieldTextInput("器灵"),"SPIRIT");
      this.appendDummyInput().appendField("模型").appendField(new Blockly.FieldDropdown(function(){return qiLingCatalog.options(this.getValue());}),"MODEL");
      this.setPreviousStatement(true);this.setNextStatement(true);this.setColour("#5d758e");
      this.setTooltip("向当前仿真机械臂载入独立器灵，选择模型并命名。载入后连接发送消息积木。");
    }};
    Blockly.Blocks[QILING_SEND]={init(this:Blockly.Block) {
      this.appendValueInput("MESSAGE").setCheck("String").appendField("向").appendField(new Blockly.FieldDropdown(function(){
        const block=this.getSourceBlock();
        const names=[...new Set(["器灵",...(block?.workspace.getBlocksByType(QILING_LOAD,false)??[]).map(x=>String(x.getFieldValue("SPIRIT")).trim()).filter(Boolean),this.getValue()].filter(Boolean))];
        return names.map(name=>[name,name] as [string,string]);
      }),"SPIRIT").appendField("发送");
      this.setInputsInline(true);this.setPreviousStatement(true);this.setNextStatement(true);this.setColour("#5d758e");
      this.setOnChange(()=>{const field=this.getInputTargetBlock("MESSAGE")?.getField("TEXT");
        if(field&&field.maxDisplayLength!==18){field.maxDisplayLength=18;field.forceRerender();}
      });
      this.setTooltip("向已载入的器灵发送消息；器灵会在机械臂旁冒泡回复。");
    }};
    const client="__import__('xiaoxia_core.blocks.qiling', fromlist=['QiLingBlock']).QiLingBlock()";
    pythonGenerator.forBlock[QILING_LOAD]=block=>`${client}.load(node_id=${JSON.stringify(block.id)}, name=${JSON.stringify(block.getFieldValue("SPIRIT"))}, target=${JSON.stringify(block.getFieldValue("TARGET"))}, model=${JSON.stringify(block.getFieldValue("MODEL"))})\n`;
    pythonGenerator.forBlock[QILING_SEND]=(block,generator)=>`${client}.send(node_id=${JSON.stringify(block.id)}, name=${JSON.stringify(block.getFieldValue("SPIRIT"))}, message=${generator.valueToCode(block,"MESSAGE",Order.NONE)||"''"})\n`;
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
    if(event.type==="started")this.speaking.set(event.node_id,event);
    if(event.type==="completed"||event.type==="error")this.speaking.delete(event.node_id);
    window.dispatchEvent(new CustomEvent("table:qiling-speech",{detail:event}));
    if(event.type==="tool_started"&&event.call_id){this.calls.add(event.call_id);agentCursor.toolStarted(event.call_id,event.name??"");}
    if(event.type==="tool_completed"&&event.call_id){this.calls.delete(event.call_id);agentCursor.finish(`tool:${event.call_id}`,event.failed);}
    if(event.type==="completed"||event.type==="error")this.finish();
    const block=workspace?.getBlockById(event.node_id);if(!block||!QILING_TYPES.includes(block.type))return;
    let text=this.replies.get(event.node_id)??"";
    if(event.type==="started"){text="";this.replies.set(event.node_id,"");}
    if(event.type==="delta"){text+=event.delta??"";this.replies.set(event.node_id,text);}
    if(event.type==="completed"){text=event.result?.text??text;this.replies.set(event.node_id,text);}
    const display=event.type==="error"?(event.text??"本轮未完成"):event.type==="tool_started"?ToolPresentation.describe(event.name??"")[0]:text||"处理中…";
    Blockly.Events.disable();
    try {if(block.getField("REPLY"))block.setFieldValue(display.replace(/\s+/g," ").slice(0,28)+(display.length>28?"…":""),"REPLY");block.setTooltip(event.type==="loaded"?`${event.spirit??"器灵"}已载入`:display);}
    finally {Blockly.Events.enable();}
  }
}

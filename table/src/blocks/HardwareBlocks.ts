/** 功能：显式连接和释放已验证配置的真机控制，位置积木沿用同一个 COM 目标。
 * Created on 2026-11-02; Updated on 2026-11-05
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";

export const HARDWARE_CONNECT = "table_hardware_connect";
export const HARDWARE_STOP = "table_hardware_stop";
export const HARDWARE_ENABLE = "table_hardware_enable";
export const HARDWARE_DISABLE = "table_hardware_disable";
export const HARDWARE_TYPES = [HARDWARE_ENABLE, HARDWARE_DISABLE, HARDWARE_CONNECT, HARDWARE_STOP];
export class HardwareBlocks {
  register(): void {
    for (const type of HARDWARE_TYPES) {
      Blockly.Blocks[type] = {
        init(this: Blockly.Block) {
          const labels:Record<string,string>={[HARDWARE_ENABLE]:"使能机械臂",[HARDWARE_DISABLE]:"失能机械臂",[HARDWARE_CONNECT]:"连接真机控制",[HARDWARE_STOP]:"释放真机控制"};
          this.appendDummyInput().appendField(labels[type])
            .appendField(new Blockly.FieldDropdown(function () {
              const options = armTargetCatalog.options(this.getValue()).filter(([, id]) => id !== "simulation");
              return options.length ? options : [["未发现串口", "unavailable"]];
            }), "TARGET");
          if (type === HARDWARE_CONNECT || type === HARDWARE_ENABLE) {
            this.appendDummyInput().appendField("配置").appendField(new Blockly.FieldTextInput("so100.local.yaml"), "PROFILE");
          }
          if (type === HARDWARE_CONNECT) {
            this.appendDummyInput().appendField("启用真机运动").appendField(new Blockly.FieldCheckbox("FALSE"), "ENABLE");
          }
          this.setPreviousStatement(true); this.setNextStatement(true); this.setColour("#638b80");
          if(type===HARDWARE_DISABLE)this.setTooltip("缓慢回到本次使能时的起始位置，确认失能后继续。");
        },
      };
      pythonGenerator.forBlock[type] = block => {
        const target = String(block.getFieldValue("TARGET"));
        if (!/^serial:COM[1-9][0-9]*$/.test(target)) throw new Error("请选择 COM 口");
        if (type === HARDWARE_CONNECT && block.getFieldValue("ENABLE") !== "TRUE") throw new Error("请勾选启用真机运动");
        const client = `__import__('xiaoxia_core.communication.hardware_client', fromlist=['HardwareClient']).HardwareClient(${JSON.stringify(target.slice(7))})`;
        if(type===HARDWARE_ENABLE)return `${client}.enable(${JSON.stringify(block.getFieldValue("PROFILE"))})\n`;
        if(type===HARDWARE_DISABLE)return `${client}.disable()\n`;
        return type === HARDWARE_STOP ? `${client}.stop()\n` : `${client}.connect(${JSON.stringify(block.getFieldValue("PROFILE"))}, enable_motion=True)\n`;
      };
    }
  }
}

/** 功能：显式连接和释放已验证配置的真机控制，位置积木沿用同一个 COM 目标。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { armTargetCatalog } from "./ArmTargetCatalog";

export const HARDWARE_CONNECT = "table_hardware_connect";
export const HARDWARE_STOP = "table_hardware_stop";
export const HARDWARE_TYPES = [HARDWARE_CONNECT, HARDWARE_STOP];
export class HardwareBlocks {
  register(): void {
    for (const type of HARDWARE_TYPES) {
      Blockly.Blocks[type] = {
        init(this: Blockly.Block) {
          this.appendDummyInput().appendField(type === HARDWARE_CONNECT ? "连接真机控制" : "释放真机控制")
            .appendField(new Blockly.FieldDropdown(function () {
              const options = armTargetCatalog.options(this.getValue()).filter(([, id]) => id !== "simulation");
              return options.length ? options : [["未发现串口", "unavailable"]];
            }), "TARGET");
          if (type === HARDWARE_CONNECT) {
            this.appendDummyInput().appendField("配置").appendField(new Blockly.FieldTextInput("so100.local.yaml"), "PROFILE");
            this.appendDummyInput().appendField("启用真机运动").appendField(new Blockly.FieldCheckbox("FALSE"), "ENABLE");
          }
          this.setPreviousStatement(true); this.setNextStatement(true); this.setColour("#638b80");
        },
      };
      pythonGenerator.forBlock[type] = block => {
        const target = String(block.getFieldValue("TARGET"));
        if (!/^serial:COM[1-9][0-9]*$/.test(target)) throw new Error("请选择 COM 口");
        if (type === HARDWARE_CONNECT && block.getFieldValue("ENABLE") !== "TRUE") throw new Error("请勾选启用真机运动");
        const client = `__import__('xiaoxia_core.communication.hardware_client', fromlist=['HardwareClient']).HardwareClient(${JSON.stringify(target.slice(7))})`;
        return type === HARDWARE_STOP ? `${client}.stop()\n` : `${client}.connect(${JSON.stringify(block.getFieldValue("PROFILE"))}, enable_motion=True)\n`;
      };
    }
  }
}

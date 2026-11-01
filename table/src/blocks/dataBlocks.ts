/** 功能：数据分类积木调用物理仿真与只读真机采集 API，保留异步命令回执。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";
import { cameraCatalog } from "./CameraCatalog";
import { BLOCK_TYPE, JOINTS } from "./positionBlock";

export const DATA_SIM = "table_data_simulation";
export const DATA_HARDWARE = "table_data_hardware";
export const DATA_TARGET = "table_data_joint_targets";
export const DATA_CAPTURE = "table_data_capture";
export const DATA_COMMAND = "table_data_command";
export const DATA_OPERATIONS: Record<string, [string, string]> = {
  table_data_start: ["启动采集", "start"], table_data_episode: ["保存回合", "save_episode"],
  table_data_finish: ["结束采集", "finish"], table_data_stop: ["停止采集", "stop"],
  table_data_status: ["采集状态", "session"],
};
export const DATA_TYPES = [DATA_SIM, DATA_HARDWARE, DATA_TARGET, DATA_CAPTURE, DATA_COMMAND, ...Object.keys(DATA_OPERATIONS)];
const client = "__import__('xiaoxia_core.collection.capture_client', fromlist=['CollectionClient']).CollectionClient()";
const idValue = (value: string) => `(lambda value: (value.get('id') or value.get('session_id')) if isinstance(value, dict) else value)(${value})`;

export class DataBlocks {
  register(): void {
    for (const type of DATA_TYPES) {
      Blockly.Blocks[type] = {
        init(this: Blockly.Block) {
          this.setColour("#61898d"); this.setOutput(true);
          if ([DATA_SIM, DATA_HARDWARE].includes(type)) {
            this.appendDummyInput().appendField(type === DATA_SIM ? "创建仿真采集" : "创建真机只读采集");
            this.appendDummyInput().appendField("任务").appendField(new Blockly.FieldTextInput("机械臂示教"), "TASK")
              .appendField("帧率").appendField(new Blockly.FieldNumber(10, 1, 60, 1), "FPS");
            if (type === DATA_SIM) this.appendDummyInput().appendField("采集仿真画面").appendField(new Blockly.FieldCheckbox("TRUE"), "IMAGES");
            else {
              this.appendDummyInput().appendField("配置").appendField(new Blockly.FieldTextInput("so100.local.yaml"), "PROFILE");
              this.appendDummyInput().appendField("相机").appendField(new Blockly.FieldDropdown(() => [["不采集图像", "none"], ...cameraCatalog.options().filter(([, id]) => id.startsWith("opencv_"))]), "CAMERA");
              this.appendDummyInput().appendField("确认只读采集").appendField(new Blockly.FieldCheckbox("FALSE"), "CONFIRMED");
            }
          } else if (type === DATA_TARGET) {
            this.appendDummyInput().appendField("机械臂设定角度");
          } else {
            this.appendDummyInput().appendField(type === DATA_CAPTURE ? "记录一帧" : type === DATA_COMMAND ? "采集命令状态" : DATA_OPERATIONS[type][0]);
            this.appendValueInput("SESSION").appendField("采集会话");
            if (type === DATA_CAPTURE) this.appendValueInput("ACTION").appendField("动作标签");
            if (type === DATA_COMMAND) this.appendValueInput("COMMAND").appendField("命令回执");
          }
          this.setTooltip(type === DATA_HARDWARE ? "只读编码器采集，不使能力矩；需要本机已确认且校准匹配的设备配置。" : "调用采集 API；启动和记录均异步，使用采集状态/命令状态查询完成结果。");
        },
      };
      pythonGenerator.forBlock[type] = (block, generator) => {
        let expression: string;
        if (type === DATA_TARGET) {
          const arm = block.workspace.getBlocksByType(BLOCK_TYPE, false)[0];
          if (!arm) throw new Error("机械臂设定角度需要工作区中的机械臂位置积木");
          expression = `{${JOINTS.map(([name]) => `${JSON.stringify(name)}: ${Number(arm.getFieldValue(name))}`).join(", ")}}`;
        } else if ([DATA_SIM, DATA_HARDWARE].includes(type)) {
          const common = `${JSON.stringify(block.getFieldValue("TASK"))}, fps=${block.getFieldValue("FPS")}`;
          if (type === DATA_SIM) expression = `${client}.create_simulation(${common}, cameras=${block.getFieldValue("IMAGES") === "TRUE" ? "['simulation']" : "[]"})`;
          else expression = `${client}.create_hardware(${JSON.stringify(block.getFieldValue("TASK"))}, ${JSON.stringify(block.getFieldValue("PROFILE"))}, fps=${block.getFieldValue("FPS")}, cameras=${block.getFieldValue("CAMERA") === "none" ? "[]" : `[${JSON.stringify(block.getFieldValue("CAMERA"))}]`}, read_only_confirmed=${block.getFieldValue("CONFIRMED") === "TRUE" ? "True" : "False"})`;
        } else {
          const session = idValue(generator.valueToCode(block, "SESSION", Order.NONE) || "''");
          if (type === DATA_CAPTURE) expression = `${client}.capture(${session}, action=${generator.valueToCode(block, "ACTION", Order.NONE) || "None"})`;
          else if (type === DATA_COMMAND) {
            const command = generator.valueToCode(block, "COMMAND", Order.NONE) || "0";
            expression = `${client}.command(${session}, (lambda value: value['command_id'] if isinstance(value, dict) else value)(${command}))`;
          } else expression = `${client}.${DATA_OPERATIONS[type][1]}(${session})`;
        }
        return [expression, Order.FUNCTION_CALL];
      };
    }
  }
}

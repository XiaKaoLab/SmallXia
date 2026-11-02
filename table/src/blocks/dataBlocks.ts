/** 功能：数据分类积木调用物理仿真与只读真机采集 API，保留异步命令回执。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";
import { cameraCatalog } from "./CameraCatalog";

export const DATA_SIM = "table_data_simulation";
export const DATA_HARDWARE = "table_data_hardware";
export const DATA_TARGET = "table_data_joint_targets";
export const DATA_RECORD = "table_data_record";
export const DATA_PLAY = "table_data_playback";
export const PLAYBACK_OPERATIONS: Record<string, [string, string]> = {
  table_data_playback_pause: ["暂停播放", "pause_playback"],
  table_data_playback_resume: ["继续播放", "resume_playback"],
  table_data_playback_stop: ["停止播放", "stop_playback"],
  table_data_playback_status: ["播放状态", "playback"],
  table_data_recordings: ["录制列表", "recordings"],
};
export const DATA_CAPTURE = "table_data_capture";
export const DATA_COMMAND = "table_data_command";
export const DATA_OPERATIONS: Record<string, [string, string]> = {
  table_data_start: ["启动采集", "start"], table_data_episode: ["保存回合", "save_episode"],
  table_data_finish: ["结束采集", "finish"], table_data_stop: ["停止采集", "stop"],
  table_data_status: ["采集状态", "session"],
};
export const DATA_TYPES = [DATA_SIM, DATA_HARDWARE, DATA_TARGET, DATA_RECORD, DATA_PLAY, DATA_CAPTURE, DATA_COMMAND, ...Object.keys(DATA_OPERATIONS), ...Object.keys(PLAYBACK_OPERATIONS)];
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
            this.appendDummyInput().appendField("记录动作标签").appendField(new Blockly.FieldCheckbox(type === DATA_SIM ? "TRUE" : "FALSE"), "ACTIONS");
            if (type === DATA_SIM) this.appendDummyInput().appendField("采集仿真画面").appendField(new Blockly.FieldCheckbox("TRUE"), "IMAGES");
            else {
              this.appendDummyInput().appendField("配置").appendField(new Blockly.FieldTextInput("so100.local.yaml"), "PROFILE");
              this.appendDummyInput().appendField("相机").appendField(new Blockly.FieldDropdown(() => [["不采集图像", "none"], ...cameraCatalog.options().filter(([, id]) => id.startsWith("opencv_"))]), "CAMERA");
              this.appendDummyInput().appendField("确认只读采集").appendField(new Blockly.FieldCheckbox("FALSE"), "CONFIRMED");
            }
          } else if (type === DATA_PLAY) {
            this.appendDummyInput().appendField("播放录制（仿真）")
              .appendField(new Blockly.FieldTextInput("latest_motion"), "RECORDING_ID");
            this.appendDummyInput().appendField("速度").appendField(new Blockly.FieldNumber(1, .1, 4, .1), "SPEED").appendField("倍");
          } else if (type in PLAYBACK_OPERATIONS) {
            this.appendDummyInput().appendField(PLAYBACK_OPERATIONS[type][0]);
            if (type !== "table_data_recordings") this.appendValueInput("PLAYBACK").appendField("播放回执");
          } else if (type === DATA_TARGET) {
            this.appendDummyInput().appendField("当前仿真目标角度");
          } else {
            this.appendDummyInput().appendField(type === DATA_RECORD ? "录制一段" : type === DATA_CAPTURE ? "记录一帧" : type === DATA_COMMAND ? "采集命令状态" : DATA_OPERATIONS[type][0]);
            this.appendValueInput("SESSION").appendField("采集会话");
            if (type === DATA_RECORD) this.appendDummyInput().appendField("时长").appendField(new Blockly.FieldNumber(10, 1, 3600, .1), "DURATION").appendField("秒");
            if ([DATA_CAPTURE, DATA_RECORD].includes(type)) this.appendValueInput("ACTION").appendField("动作标签");
            if (type === DATA_COMMAND) this.appendValueInput("COMMAND").appendField("命令回执");
          }
          this.setTooltip(type === DATA_PLAY ? "在仿真中播放录制。" : type === DATA_RECORD ? "录制指定时长后自动保存。" : type === DATA_HARDWARE ? "采集实机关节和相机数据。" : "管理数据采集。");
        },
      };
      pythonGenerator.forBlock[type] = (block, generator) => {
        let expression: string;
        if (type === DATA_PLAY) {
          const speed = Number(block.getFieldValue("SPEED"));
          if (!Number.isFinite(speed) || speed < .1 || speed > 4) throw new Error("播放速度须在 0.1–4 倍之间");
          expression = `${client}.play(${JSON.stringify(block.getFieldValue("RECORDING_ID"))}, speed=${speed})`;
        } else if (type in PLAYBACK_OPERATIONS) {
          const playback = idValue(generator.valueToCode(block, "PLAYBACK", Order.NONE) || "''");
          expression = type === "table_data_recordings" ? `${client}.recordings()` : `${client}.${PLAYBACK_OPERATIONS[type][1]}(${playback})`;
        } else if (type === DATA_TARGET) {
          expression = "__import__('xiaoxia_core.blocks.workflow', fromlist=['BlockWorkflow']).BlockWorkflow.http('robots/table/state')['joint_positions']";
        } else if ([DATA_SIM, DATA_HARDWARE].includes(type)) {
          const common = `${JSON.stringify(block.getFieldValue("TASK"))}, fps=${block.getFieldValue("FPS")}, record_actions=${block.getFieldValue("ACTIONS") === "TRUE" ? "True" : "False"}`;
          if (type === DATA_SIM) expression = `${client}.create_simulation(${common}, cameras=${block.getFieldValue("IMAGES") === "TRUE" ? "['simulation']" : "[]"})`;
          else expression = `${client}.create_hardware(${JSON.stringify(block.getFieldValue("TASK"))}, ${JSON.stringify(block.getFieldValue("PROFILE"))}, fps=${block.getFieldValue("FPS")}, record_actions=${block.getFieldValue("ACTIONS") === "TRUE" ? "True" : "False"}, cameras=${block.getFieldValue("CAMERA") === "none" ? "[]" : `[${JSON.stringify(block.getFieldValue("CAMERA"))}]`}, read_only_confirmed=${block.getFieldValue("CONFIRMED") === "TRUE" ? "True" : "False"})`;
        } else {
          const session = idValue(generator.valueToCode(block, "SESSION", Order.NONE) || "''");
          if (type === DATA_RECORD) {
            const duration = Number(block.getFieldValue("DURATION"));
            if (!Number.isFinite(duration) || duration < 1 || duration > 3600) throw new Error("录制时长须为 1–3600 秒");
            expression = `${client}.record(${session}, duration_s=${duration}, action=${generator.valueToCode(block, "ACTION", Order.NONE) || "None"})`;
          } else if (type === DATA_CAPTURE) expression = `${client}.capture(${session}, action=${generator.valueToCode(block, "ACTION", Order.NONE) || "None"})`;
          else if (type === DATA_COMMAND) {
            const command = generator.valueToCode(block, "COMMAND", Order.NONE) || "0";
            expression = `${client}.command(${session}, (lambda value: value['command_id'] if isinstance(value, dict) else value)(${command}))`;
          } else expression = `${client}.${DATA_OPERATIONS[type][1]}(${session})`;
        }
        if (type === DATA_PLAY) expression = `(lambda receipt: (print(__import__('json').dumps({'data_playback': receipt}, ensure_ascii=False)), receipt)[1])(${expression})`;
        if (type === DATA_RECORD) expression = `(lambda receipt: (print(__import__('json').dumps({'data_recording': receipt}, ensure_ascii=False)), receipt)[1])(${expression})`;
        return [expression, Order.FUNCTION_CALL];
      };
    }
  }
}

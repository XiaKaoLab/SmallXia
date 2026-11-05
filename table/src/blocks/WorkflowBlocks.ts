/** 功能：简洁示教到推理流程、等待及红球视觉积木，隐藏会话管理细节。
 * Created on 2026-11-02; Updated on 2026-11-05
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";
import { workflowCatalog } from "./WorkflowCatalog";
import { armTargetCatalog } from "./ArmTargetCatalog";
import { cameraCatalog } from "./CameraCatalog";
import { PolicyTargetFields } from "./PolicyTargetFields";
import { RedTrackingBlocks } from "./RedTrackingBlocks";

export const DEMO_BEGIN = "table_demo_begin";
export const DEMO_RECORD = "table_demo_record";
export const DEMO_FINISH = "table_demo_finish";
export const DEMO_TRAIN = "table_demo_train";
export const DEMO_RUN = "table_demo_run";
export const WAIT = "table_wait";
export const RED_DETECT = "table_detect_red_ball";
export const RED_VALUE = "table_red_ball_value";
export const WAIT_RESULT = "table_wait_result";
export const DEMO_HARDWARE = "table_demo_hardware";
export const DEMO_PLAY = "table_demo_play";
export const WORKFLOW_TYPES = [DEMO_PLAY, DEMO_HARDWARE, DEMO_BEGIN, DEMO_RECORD, DEMO_FINISH, DEMO_TRAIN, DEMO_RUN, WAIT, WAIT_RESULT, RED_DETECT, RED_VALUE];
const workflow = "__import__('xiaoxia_core.blocks.workflow', fromlist=['BlockWorkflow']).BlockWorkflow()";

export class WorkflowBlocks {
  register(): void {
    RedTrackingBlocks.register();
    for (const type of WORKFLOW_TYPES) {
      Blockly.Blocks[type] = {
        init(this: Blockly.Block) {
          this.setColour([DEMO_BEGIN, DEMO_RECORD, DEMO_FINISH].includes(type) ? "#61898d" : "#7d7297");
          if (type === DEMO_HARDWARE) {
            this.appendDummyInput().appendField("录制真机示教")
              .appendField(new Blockly.FieldDropdown(function () {
                const options = armTargetCatalog.options(this.getValue()).filter(([, id]) => id !== 'simulation');
                return options.length ? options : [["未发现串口", "unavailable"]];
              }), "TARGET");
            this.appendDummyInput().appendField("时长").appendField(new Blockly.FieldNumber(10, 1, 3600, .5), "SECONDS").appendField("秒");
            this.appendDummyInput().appendField("相机").appendField(new Blockly.FieldDropdown(function () {
              return [["不录制画面", "none"], ...cameraCatalog.options(this.getValue()).filter(([, id]) => id.startsWith('opencv_'))];
            }), "CAMERA");
          } else if (type === DEMO_BEGIN) {
            this.appendDummyInput().appendField("开始示教").appendField(new Blockly.FieldTextInput("机械臂示教"), "TASK");
            this.appendDummyInput().appendField("画面").appendField(new Blockly.FieldDropdown(function () {
              return [["不录制", "none"], ["腕部虚拟相机", "virtual"], ...cameraCatalog.realOptions(this.getValue()).filter(([, id]) => id.startsWith('opencv_'))];
            }), "CAMERA");
          } else if (type === DEMO_RECORD) this.appendDummyInput().appendField("记录当前仿真姿态");
          else if (type === DEMO_FINISH) this.appendDummyInput().appendField("保存示教");
          else if (type === DEMO_PLAY) {
            this.appendDummyInput().appendField("回放示教动作（仿真）").appendField(new Blockly.FieldDropdown(function () {
              return workflowCatalog.options('datasets', this.getValue());
            }), 'ID');
          } else if ([DEMO_TRAIN, DEMO_RUN].includes(type)) {
            this.appendDummyInput().appendField(type === DEMO_TRAIN ? "训练示教模型" : "运行示教模型")
              .appendField(new Blockly.FieldDropdown(function () { return workflowCatalog.options(type === DEMO_TRAIN ? "datasets" : "models", this.getValue()); }), "ID");
            this.appendDummyInput().appendField(type === DEMO_TRAIN ? "训练步数" : "运行步数")
              .appendField(new Blockly.FieldNumber(type === DEMO_TRAIN ? 1000 : 20, 1, type === DEMO_TRAIN ? 1000000 : 1000, 1), "STEPS")
              .appendField(new Blockly.FieldDropdown([["CPU", "cpu"], ["CUDA", "cuda"]]), "DEVICE");
            if(type===DEMO_RUN)PolicyTargetFields.append(this);
          } else if (type === WAIT) {
            this.appendDummyInput().appendField("等待").appendField(new Blockly.FieldNumber(.3, 0, 3600, .1), "SECONDS").appendField("秒");
          } else if (type === WAIT_RESULT) this.appendValueInput("RECEIPT").appendField("等待任务完成");
          else if (type === RED_DETECT) {
            this.appendValueInput("FRAME").setCheck("CameraFrame").appendField("识别画面中的红球");
          } else if (type === RED_VALUE) {
            this.appendValueInput("RESULT").appendField("红球结果");
            this.appendDummyInput().appendField(new Blockly.FieldDropdown([["找到", "found"], ["横坐标（0–1）", "normalized_x"], ["纵坐标（0–1）", "normalized_y"], ["半径（像素）", "radius"], ["面积（像素）", "area"]]), "KEY");
          }
          if ([RED_DETECT, RED_VALUE].includes(type)) this.setOutput(true);
          else { this.setPreviousStatement(true); this.setNextStatement(true); }
        },
      };
      pythonGenerator.forBlock[type] = (block, generator) => {
        if (type === DEMO_HARDWARE) {
          const target = String(block.getFieldValue("TARGET"));
          if (!/^serial:COM[1-9][0-9]*$/.test(target)) throw new Error("请选择 COM 口");
          return `__import__('xiaoxia_core.blocks.manual_teaching', fromlist=['ManualTeaching']).ManualTeaching().record(${JSON.stringify(target.slice(7))}, seconds=${block.getFieldValue('SECONDS')}, camera=${JSON.stringify(block.getFieldValue('CAMERA'))})\n`;
        }
        if (type === RED_DETECT) {
          const frame = generator.valueToCode(block, "FRAME", Order.NONE);
          if (!frame) throw new Error("请接入画面变量");
          return [`__import__('xiaoxia_core.collection.red_ball', fromlist=['RedBallDetector']).RedBallDetector().detect(${frame})`, Order.FUNCTION_CALL];
        }
        if (type === RED_VALUE) {
          const result = generator.valueToCode(block, "RESULT", Order.NONE);
          if (!result) throw new Error("请接入红球识别结果");
          return [`(${result}).get(${JSON.stringify(block.getFieldValue("KEY"))})`, Order.FUNCTION_CALL];
        }
        if (type === WAIT) return `for _block_wait in range(${Math.ceil(Number(block.getFieldValue("SECONDS")) * 20)}):\n    __import__('time').sleep(0.05)\n`;
        if (type === WAIT_RESULT) {
          const receipt = generator.valueToCode(block, "RECEIPT", Order.NONE);
          if (!receipt) throw new Error("请接入任务回执");
          return `${workflow}.wait_result(${receipt})\n`;
        }
        if (type === DEMO_BEGIN) return `${workflow}.begin(${JSON.stringify(block.getFieldValue("TASK"))}, ${JSON.stringify(block.getFieldValue("CAMERA"))})\n`;
        if (type === DEMO_RECORD) return `${workflow}.record_pose()\n`;
        if (type === DEMO_FINISH) return `${workflow}.finish()\n`;
        if (type === DEMO_PLAY) return `${workflow}.play(${JSON.stringify(block.getFieldValue('ID'))})\n`;
        const method = type === DEMO_TRAIN ? "train" : "run";
        const target=type===DEMO_RUN?`, ${PolicyTargetFields.arguments(block)}`:"";
        return `${workflow}.${method}(${JSON.stringify(block.getFieldValue("ID"))}, steps=${block.getFieldValue("STEPS")}, device=${JSON.stringify(block.getFieldValue("DEVICE"))}${target})\n`;
      };
    }
  }
}

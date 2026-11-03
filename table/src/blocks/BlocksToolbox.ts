/** 功能：统一 Blockly 工具箱及允许使用的积木目录。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { QILING_LOAD, QILING_SEND, QILING_TYPES } from "./QiLingBlocks";
import { TEXT_READ, TEXT_PICK, TEXT_VISION_TYPES } from "./TextVisionBlocks";
import { CAMERA_CALIBRATION_BLOCK } from "./cameraCalibrationBlock";
import { ARM_MAPPING_BLOCK } from "./armMappingBlock";
import { CALIBRATION_BLOCK } from "./calibrationBlock";
import type * as Blockly from "blockly/core";
import { DATA_TYPES, DATA_PLAY, PLAYBACK_OPERATIONS, DATA_SIM, DATA_HARDWARE, DATA_TARGET, DATA_RECORD, DATA_CAPTURE, DATA_COMMAND, DATA_OPERATIONS } from "./dataBlocks";
import { BLOCK_TYPE } from "./positionBlock";
import { CAMERA_BLOCK_TYPE } from "./cameraBlock";
import { FRAME_CAPTURE, FRAME_VARIABLE } from "./frameBlocks";
import { POLICY_TRAIN, POLICY_PREDICT, POLICY_ROLLOUT, POLICY_JOB, POLICY_STOP, POLICY_RL_BALL } from "./policyBlocks";
import { ONNX_TYPES } from "./OnnxPolicyBlocks";
import { HARDWARE_TYPES } from "./HardwareBlocks";
import { DEMO_PLAY, DEMO_HARDWARE, DEMO_BEGIN, DEMO_RECORD, DEMO_FINISH, DEMO_TRAIN, DEMO_RUN, WAIT, WAIT_RESULT, RED_DETECT, RED_VALUE, WORKFLOW_TYPES } from "./WorkflowBlocks";

export const LOGIC_TYPES = ["controls_if", "controls_repeat_ext", "controls_whileUntil", "controls_flow_statements", "logic_compare", "logic_operation", "logic_negate", "logic_boolean", "logic_ternary", "math_arithmetic", "procedures_defnoreturn", "procedures_defreturn", "procedures_callnoreturn", "procedures_callreturn", "procedures_ifreturn"];
export const VARIABLE_TYPES = ["variables_get", "variables_set", "text", "math_number"];
export const TOOLBOX_TYPES = [...QILING_TYPES, ...HARDWARE_TYPES, ...TEXT_VISION_TYPES, ...WORKFLOW_TYPES, ARM_MAPPING_BLOCK, CAMERA_CALIBRATION_BLOCK, CALIBRATION_BLOCK, BLOCK_TYPE, CAMERA_BLOCK_TYPE, FRAME_CAPTURE, FRAME_VARIABLE,
  ...LOGIC_TYPES, ...VARIABLE_TYPES, ...DATA_TYPES, ...ONNX_TYPES, POLICY_TRAIN, POLICY_PREDICT, POLICY_ROLLOUT, POLICY_JOB, POLICY_STOP, POLICY_RL_BALL];
export const BLOCK_LIMITS: Record<string, number> = { [ARM_MAPPING_BLOCK]: 1, [CAMERA_CALIBRATION_BLOCK]: 1, [CALIBRATION_BLOCK]: 1, [CAMERA_BLOCK_TYPE]: 1 };
const block = (type: string) => ({ kind: "block", type,
  ...(type === 'controls_repeat_ext' ? { inputs: { TIMES: { shadow: { type: 'math_number', fields: { NUM: 10 } } } } } : {}) });
const policy = (type: string) => ({ kind: "block", type, inputs: { ID: { shadow: { type: "text", fields: { TEXT: "" } } } } });

export class BlocksToolbox {
  definition(): Blockly.utils.toolbox.ToolboxInfo {
    return { kind: "categoryToolbox", contents: [
      { kind: "category", name: "器灵", colour: "#5d758e", contents: [
        { kind: "button", text: "刷新模型", callbackkey: "REFRESH_QILING_MODELS" },
        block(QILING_LOAD),
        { kind: "block", type: QILING_SEND, inputs: { MESSAGE: { shadow: { type: "text", fields: { TEXT: "你好" } } } } },
      ] },
      { kind: "category", name: "机械臂", colour: "#638b80", contents: [{ kind: "button", text: "刷新串口", callbackkey: "REFRESH_ARM_PORTS" }, block(BLOCK_TYPE), block(CALIBRATION_BLOCK), block(ARM_MAPPING_BLOCK), ...HARDWARE_TYPES.map(block)] },
      { kind: "category", name: "相机", colour: "#587e9d", contents: [{ kind: "button", text: "刷新相机", callbackkey: "REFRESH_CAMERAS" }, block(CAMERA_BLOCK_TYPE), block(FRAME_CAPTURE), block(RED_DETECT), block(RED_VALUE), block(TEXT_READ), block(CAMERA_CALIBRATION_BLOCK)] },
      { kind: "category", name: "逻辑", colour: "#687f9b", contents: [block(WAIT), block(WAIT_RESULT), ...LOGIC_TYPES.filter(type => !type.startsWith('procedures_call')).map(block)] },
      { kind: "category", name: "变量", colour: "#9a805c", contents: [
        { kind: "button", text: "创建变量", callbackkey: "CREATE_VARIABLE" },
        block("variables_set"), block("variables_get"), block(FRAME_VARIABLE), block("text"), block("math_number"),
      ] },
      { kind: "category", name: "策略", colour: "#7d7297", contents: [
        { kind: "button", text: "刷新示教与模型", callbackkey: "REFRESH_WORKFLOW" }, block(DEMO_TRAIN), block(DEMO_RUN),
        { kind: "button", text: "刷新抓球模型", callbackkey: "REFRESH_ONNX_MODELS" }, block(POLICY_RL_BALL), block(TEXT_PICK), ...ONNX_TYPES.map(block),
        { kind: "category", name: "高级策略", colour: "#7d7297", contents: [POLICY_TRAIN, POLICY_PREDICT, POLICY_ROLLOUT, POLICY_JOB, POLICY_STOP].map(policy) },
      ] },
      { kind: "category", name: "数据", colour: "#61898d", contents: [
        { kind: "button", text: "插入示教流程", callbackkey: "INSERT_DEMO_FLOW" },
        block(DEMO_BEGIN), block(DEMO_RECORD), block(DEMO_FINISH), block(DEMO_HARDWARE), block(DEMO_PLAY),
        { kind: "category", name: "高级采集", colour: "#61898d", contents: [block(DATA_SIM), block(DATA_HARDWARE),
        { kind: "block", type: DATA_RECORD, inputs: { SESSION: { shadow: { type: "text", fields: { TEXT: "" } } } } },
        ...Object.keys(DATA_OPERATIONS).map(type => ({ kind: "block", type, inputs: { SESSION: { shadow: { type: "text", fields: { TEXT: "" } } } } })),
        { kind: "block", type: DATA_CAPTURE, inputs: { SESSION: { shadow: { type: "text", fields: { TEXT: "" } } }, ACTION: { shadow: { type: DATA_TARGET } } } },
        block(DATA_TARGET), block(DATA_COMMAND), block(DATA_PLAY), ...Object.keys(PLAYBACK_OPERATIONS).map(block)] },
      ] },
    ] };
  }
}

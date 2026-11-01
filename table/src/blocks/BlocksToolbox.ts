/** 功能：统一六类 Blockly 工具箱及允许使用的积木目录。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import type * as Blockly from "blockly/core";
import { DATA_TYPES, DATA_SIM, DATA_HARDWARE, DATA_TARGET, DATA_CAPTURE, DATA_COMMAND, DATA_OPERATIONS } from "./dataBlocks";
import { BLOCK_TYPE } from "./positionBlock";
import { CAMERA_BLOCK_TYPE } from "./cameraBlock";
import { FRAME_CAPTURE, FRAME_VARIABLE } from "./frameBlocks";
import { POLICY_TRAIN, POLICY_PREDICT, POLICY_ROLLOUT, POLICY_JOB, POLICY_STOP, POLICY_RL_BALL } from "./policyBlocks";
import { ONNX_TYPES } from "./OnnxPolicyBlocks";

export const LOGIC_TYPES = ["controls_if", "logic_compare", "logic_operation", "logic_negate", "logic_boolean", "logic_ternary"];
export const VARIABLE_TYPES = ["variables_get", "variables_set", "text", "math_number"];
export const TOOLBOX_TYPES = [BLOCK_TYPE, CAMERA_BLOCK_TYPE, FRAME_CAPTURE, FRAME_VARIABLE,
  ...LOGIC_TYPES, ...VARIABLE_TYPES, ...DATA_TYPES, ...ONNX_TYPES, POLICY_TRAIN, POLICY_PREDICT, POLICY_ROLLOUT, POLICY_JOB, POLICY_STOP, POLICY_RL_BALL];
export const BLOCK_LIMITS: Record<string, number> = { [BLOCK_TYPE]: 1, [CAMERA_BLOCK_TYPE]: 1, [FRAME_CAPTURE]: 2, [FRAME_VARIABLE]: 2 };
const block = (type: string) => ({ kind: "block", type });
const policy = (type: string) => ({ kind: "block", type, inputs: { ID: { shadow: { type: "text", fields: { TEXT: "" } } } } });

export class BlocksToolbox {
  definition(): Blockly.utils.toolbox.ToolboxInfo {
    return { kind: "categoryToolbox", contents: [
      { kind: "category", name: "机械臂", colour: "#638b80", contents: [block(BLOCK_TYPE)] },
      { kind: "category", name: "相机", colour: "#587e9d", contents: [{ kind: "button", text: "刷新相机", callbackkey: "REFRESH_CAMERAS" }, block(CAMERA_BLOCK_TYPE), block(FRAME_CAPTURE)] },
      { kind: "category", name: "逻辑", colour: "#687f9b", contents: LOGIC_TYPES.map(block) },
      { kind: "category", name: "变量", colour: "#9a805c", contents: [
        { kind: "button", text: "创建变量", callbackkey: "CREATE_VARIABLE" },
        block("variables_set"), block("variables_get"), block(FRAME_VARIABLE), block("text"), block("math_number"),
      ] },
      { kind: "category", name: "策略", colour: "#7d7297", contents: [block(POLICY_RL_BALL), ...ONNX_TYPES.map(block), ...[POLICY_TRAIN, POLICY_PREDICT, POLICY_ROLLOUT, POLICY_JOB, POLICY_STOP].map(policy)] },
      { kind: "category", name: "数据", colour: "#61898d", contents: [block(DATA_SIM), block(DATA_HARDWARE),
        ...Object.keys(DATA_OPERATIONS).map(type => ({ kind: "block", type, inputs: { SESSION: { shadow: { type: "text", fields: { TEXT: "" } } } } })),
        { kind: "block", type: DATA_CAPTURE, inputs: { SESSION: { shadow: { type: "text", fields: { TEXT: "" } } }, ACTION: { shadow: { type: DATA_TARGET } } } },
        block(DATA_TARGET), block(DATA_COMMAND)] },
    ] };
  }
}

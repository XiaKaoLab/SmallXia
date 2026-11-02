/** 功能：策略积木通过既有模仿学习客户端创建任务、查询状态和停止任务。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";
import { OnnxPolicyBlocks } from "./OnnxPolicyBlocks";

export const POLICY_TRAIN = "table_policy_train";
export const POLICY_PREDICT = "table_policy_predict";
export const POLICY_ROLLOUT = "table_policy_rollout";
export const POLICY_JOB = "table_policy_job";
export const POLICY_STOP = "table_policy_stop";
export const POLICY_RL_BALL = "table_policy_rl_ball";
export const POLICY_TYPES = [POLICY_TRAIN, POLICY_PREDICT, POLICY_ROLLOUT, POLICY_JOB, POLICY_STOP, POLICY_RL_BALL];

export class PolicyBlocks {
  register(): void {
    new OnnxPolicyBlocks().register();
    Blockly.Blocks[POLICY_RL_BALL] = {
      init(this: Blockly.Block) {
        this.appendDummyInput().appendField("强化学习 · 拿取小球");
        this.appendDummyInput().appendField("同时训练").appendField(new Blockly.FieldNumber(4, 1, 16, 1), "NUM_ENVS").appendField("个");
        this.appendDummyInput().appendField("每个训练").appendField(new Blockly.FieldNumber(100, 1, 10000, 1), "ROUNDS").appendField("轮");
        this.appendDummyInput().appendField("设备").appendField(new Blockly.FieldDropdown([["CPU", "cpu"], ["CUDA", "cuda"]]), "DEVICE");
        this.setPreviousStatement(true); this.setNextStatement(true); this.setColour("#7d7297");
        this.setTooltip("训练抓球策略。");
      },
    };
    pythonGenerator.forBlock[POLICY_RL_BALL] = block =>
      `_ball_job = __import__('xiaoxia_core.reinforcement.client', fromlist=['ReinforcementClient']).ReinforcementClient().train_ball(num_envs=${block.getFieldValue("NUM_ENVS")}, rounds=${block.getFieldValue("ROUNDS")}, device=${JSON.stringify(block.getFieldValue("DEVICE"))})\nprint(__import__('json').dumps({'ball_training': _ball_job}), flush=True)\n__import__('xiaoxia_core.blocks.workflow', fromlist=['BlockWorkflow']).BlockWorkflow().wait_job(_ball_job, 'reinforcement')\n`;
    for (const type of POLICY_TYPES) {
      if (type === POLICY_RL_BALL) continue;
      Blockly.Blocks[type] = {
        init(this: Blockly.Block) {
          const labels: Record<string, string> = { [POLICY_TRAIN]: "训练策略", [POLICY_PREDICT]: "预测动作",
            [POLICY_ROLLOUT]: "运行策略", [POLICY_JOB]: "任务状态", [POLICY_STOP]: "停止任务" };
          this.appendDummyInput().appendField(labels[type]);
          this.appendValueInput("ID").appendField(type === POLICY_TRAIN ? "数据集" : [POLICY_PREDICT, POLICY_ROLLOUT].includes(type) ? "训练任务" : "任务");
          if (type === POLICY_TRAIN) {
            this.appendDummyInput().appendField("步数").appendField(new Blockly.FieldNumber(1000, 1, 1000000, 1), "STEPS")
              .appendField(new Blockly.FieldDropdown([["CPU", "cpu"], ["CUDA", "cuda"]]), "DEVICE");
          }
          if (type === POLICY_ROLLOUT) this.appendDummyInput().appendField("步数")
            .appendField(new Blockly.FieldNumber(10, 1, 1000, 1), "STEPS");
          this.setColour("#7d7297");
          if (type === POLICY_STOP) { this.setPreviousStatement(true); this.setNextStatement(true); }
          else this.setOutput(true);
          this.setTooltip(type === POLICY_ROLLOUT ? "在仿真中运行策略。" : "启动模仿学习任务。");
        },
      };
      pythonGenerator.forBlock[type] = (block, generator) => {
        const rawId = generator.valueToCode(block, "ID", Order.NONE) || "''";
        const id = `(lambda value: value["id"] if isinstance(value, dict) else value)(${rawId})`;
        const client = "__import__('xiaoxia_core.imitation.api_client', fromlist=['ImitationClient']).ImitationClient()";
        let expression: string;
        if (type === POLICY_TRAIN) expression = `${client}.train(${id}, steps=${block.getFieldValue("STEPS")}, device=${JSON.stringify(block.getFieldValue("DEVICE"))})`;
        else if (type === POLICY_PREDICT) expression = `${client}.predict(${id})`;
        else if (type === POLICY_ROLLOUT) expression = `${client}.rollout(${id}, steps=${block.getFieldValue("STEPS")})`;
        else if (type === POLICY_JOB) expression = `${client}.job(${id})`;
        else return `${client}.stop(${id})\n`;
        return [expression, Order.FUNCTION_CALL];
      };
    }
  }
}

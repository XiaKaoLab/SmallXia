/** 功能：在积木实际执行时报告机械臂视图目标，支持分支、循环与混合目标链。
 * Created on 2026-11-08; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
import { pythonGenerator } from "blockly/python";
import { DEMO_PLAY } from "./WorkflowBlocks";
import { POLICY_RL_BALL } from "./policyBlocks";
import { ONNX_RUN } from "./OnnxPolicyBlocks";
import { DATA_PLAY } from "./dataBlocks";

export class BlockViewRouting {
  private static readonly wrapped = new WeakSet<Function>();
  register(): void {
    const simulation = new Set([DEMO_PLAY, POLICY_RL_BALL, ONNX_RUN, DATA_PLAY]);
    for (const [type, generate] of Object.entries(pythonGenerator.forBlock)) {
      if (BlockViewRouting.wrapped.has(generate)) continue;
      const routed: typeof generate = (block, generator) => {
        const code = generate(block, generator);
        const target = block.getField("TARGET") ? String(block.getFieldValue("TARGET")) : simulation.has(type) ? "simulation" : "";
        if (typeof code !== "string" || (target !== "simulation" && !/^serial:COM[1-9][0-9]*$/.test(target))) return code;
        const receipt = JSON.stringify({ robot_view: { target, block_id: block.id } });
        return `print(${JSON.stringify(receipt)}, flush=True)\n${code}`;
      };
      BlockViewRouting.wrapped.add(routed);
      pythonGenerator.forBlock[type] = routed;
    }
  }
}

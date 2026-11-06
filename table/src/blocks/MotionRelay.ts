/** 功能：读取选中动作链，让器灵生成接龙并以可撤销的一组真实积木追加。
 * Created on 2026-11-06; Updated on 2026-11-06
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { agentClient } from "../chat/AgentClient";
import { BLOCK_TYPE, JOINTS } from "./positionBlock";
import { WAIT } from "./WorkflowBlocks";
import { QILING_LOAD } from "./QiLingBlocks";

interface RelayStep { offsets_deg: Record<string, number>; seconds: number }
interface RelayPlan { steps: RelayStep[]; text: string }

export class MotionRelay {
  async append(workspace: Blockly.WorkspaceSvg, isCurrent: () => boolean): Promise<string> {
    if (!agentClient.desktop) throw new Error("请在桌面应用中接龙");
    const selected = Blockly.common.getSelected();
    const roots = workspace.getTopBlocks(true).filter(root => root.getDescendants(false).some(b => b.type === BLOCK_TYPE));
    const root = selected instanceof Blockly.BlockSvg && selected.workspace === workspace
      && roots.includes(selected.getRootBlock() as Blockly.BlockSvg) ? selected.getRootBlock() as Blockly.BlockSvg : roots.length === 1 ? roots[0] : undefined;
    if (!root) throw new Error(roots.length ? "请选择要接龙的动作链" : "先放一块机械臂动作积木");
    const chain: Blockly.BlockSvg[] = [];
    for (let b: Blockly.BlockSvg | null = root; b; b = b.getNextBlock()) chain.push(b);
    if (chain.some(b => ![BLOCK_TYPE, WAIT, QILING_LOAD].includes(b.type) || !b.isEnabled())) throw new Error("请选择由机械臂动作和等待组成的动作链");
    const motions = chain.filter(b => b.type === BLOCK_TYPE);
    if (!motions.length) throw new Error("先编一个机械臂动作");
    const target = String(motions[0].getFieldValue("TARGET"));
    if (motions.some(b => b.getFieldValue("TARGET") !== target)) throw new Error("一段接龙使用同一个机械臂");
    if (workspace.remainingCapacity() < 10) throw new Error("工作区至少需要留出10块积木的位置");
    const tail = chain[chain.length - 1];
    if (!tail.nextConnection) throw new Error("这段动作不能继续拼接");
    const positions = motions.slice(-8).map(b => Object.fromEntries(JOINTS.map(([n]) => [n, Number(b.getFieldValue(n))])));
    const before = JSON.stringify(Blockly.serialization.workspaces.save(workspace));
    const node = `relay:${root.id}`;
    const speech = (type: string, text?: string) => window.dispatchEvent(new CustomEvent("table:qiling-speech", {
      detail: { type, node_id: node, spirit: "器灵", target, ...(type === "completed" ? { result: { text } } : { text }) },
    }));
    speech("started");
    try {
      const history = motions.map(b => b.getCommentText()).filter(Boolean).slice(-5);
      const model = chain.find(b => b.type === QILING_LOAD)?.getFieldValue("MODEL") || "default";
      const plan = await agentClient.request<RelayPlan>({ action: "motion_relay", poses: positions, waits: motions.slice(-8).map(b => b.getNextBlock()?.type === WAIT ? Number(b.getNextBlock()!.getFieldValue("SECONDS")) : 0), previous_ideas: history, model });
      if (!isCurrent() || JSON.stringify(Blockly.serialization.workspaces.save(workspace)) !== before) throw new Error("动作已修改，请重新接龙");
      if (!Array.isArray(plan.steps) || plan.steps.length < 2 || plan.steps.length > 4 || typeof plan.text !== "string") throw new Error("接龙结果不完整");
      const base = positions[positions.length - 1];
      const poses = [...plan.steps, { offsets_deg: {}, seconds: .8 }].map(step => {
        if (!Number.isFinite(step.seconds) || step.seconds < .5 || step.seconds > 3) throw new Error("接龙停顿无效");
        const fields = Object.fromEntries(JOINTS.map(([n]) => {
          const delta = step.offsets_deg[n] ?? 0;
          if (!Number.isFinite(delta) || Math.abs(delta) > 12) throw new Error("接龙偏移无效");
          const field = motions[motions.length - 1].getField(n) as Blockly.FieldNumber;
          return [n, Math.max(field.getMin(), Math.min(field.getMax(), base[n] + delta * Math.PI / 180))];
        }));
        return { fields, seconds: step.seconds };
      });
      if (poses.every(p => JOINTS.every(([n]) => Math.abs(p.fields[n] - base[n]) < .001))) throw new Error("这个姿态没有接龙空间，请换一个动作");
      const created: Blockly.BlockSvg[] = [];
      Blockly.Events.setGroup(true);
      try {
        let previous = tail;
        for (const pose of poses) {
          const block = workspace.newBlock(BLOCK_TYPE);
          created.push(block); block.setFieldValue(target, "TARGET");
          for (const [name, value] of Object.entries(pose.fields)) block.setFieldValue(String(value), name);
          if (block.getFieldValue("TARGET") !== target) throw new Error("机械臂目标不可用");
          block.setCommentText(`器灵接龙：${plan.text}`);
          block.initSvg(); block.render(); previous.nextConnection!.connect(block.previousConnection!);
          const wait = workspace.newBlock(WAIT); created.push(wait);
          wait.setFieldValue(String(pose.seconds), "SECONDS"); wait.initSvg(); wait.render();
          block.nextConnection!.connect(wait.previousConnection!); previous = wait;
        }
        created[0].select(); workspace.centerOnBlock(created[0].id);
      } catch (error) {
        for (const block of created.reverse()) if (workspace.getBlockById(block.id)) block.dispose(false);
        throw error;
      } finally { Blockly.Events.setGroup(false); }
      speech("completed", plan.text);
      return "已接好，轮到你了";
    } catch (error) { speech("error", "这次没接上，再试一次。"); throw error; }
  }
}

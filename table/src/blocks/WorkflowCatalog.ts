/** 功能：提供已保存示教和已完成模型的下拉选项，无需输入任务 ID。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { agentClient } from "../chat/AgentClient";

interface Entry { id: string; label: string }
export class WorkflowCatalog {
  private data: { datasets: Entry[]; models: Entry[] } = { datasets: [], models: [] };
  private pending = false;
  private workspace?: Blockly.WorkspaceSvg;
  options(kind: "datasets" | "models", selected?: string | null): [string, string][] {
    const options: [string, string][] = [[kind === "datasets" ? "最近保存的示教" : "最近训练的模型", "latest"],
      ...this.data[kind].map(row => [row.label, row.id] as [string, string])];
    if (selected && !options.some(([, id]) => id === selected)) options.push(["已选项（不可用）", selected]);
    return options;
  }
  async refresh(): Promise<void> {
    if (this.pending || !agentClient.desktop) return;
    this.pending = true;
    try {
      this.data = await agentClient.request({ action: "workflow_catalog" });
      const workspace = this.workspace;
      if (!workspace || workspace.isDragging()) return;
      for (const block of [...workspace.getAllBlocks(false), ...(workspace.getFlyout()?.getWorkspace().getAllBlocks(false) ?? [])]) {
        if (!["table_demo_train", "table_demo_run", "table_demo_play"].includes(block.type)) continue;
        const field = block.getField("ID") as Blockly.FieldDropdown;
        const selected = field.getValue();
        field.setOptions(() => this.options(block.type === "table_demo_run" ? "models" : "datasets", field.getValue()));
        field.setValue(selected); field.forceRerender();
      }
    }
    finally { this.pending = false; }
  }
  attach(workspace: Blockly.WorkspaceSvg): () => void {
    this.workspace = workspace;
    workspace.registerButtonCallback("REFRESH_WORKFLOW", () => { void this.refresh().catch(() => undefined); });
    void this.refresh().catch(() => undefined);
    const timer = setInterval(() => void this.refresh().catch(() => undefined), 10000);
    return () => { clearInterval(timer); if (this.workspace === workspace) this.workspace = undefined; };
  }
}
export const workflowCatalog = new WorkflowCatalog();

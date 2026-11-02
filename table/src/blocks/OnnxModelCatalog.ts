/** 功能：发现同环境的已训练模型，为策略积木提供动态下拉选项。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { agentClient } from "../chat/AgentClient";

interface Model { id: string; label: string; exported: boolean; compatible: boolean }
export class OnnxModelCatalog {
  private models: Model[] = [];
  private pending = false;
  private workspace?: Blockly.WorkspaceSvg;

  options(exported: boolean, selected?: string | null): [string, string][] {
    const models = this.models.filter(model => model.compatible && (!exported || model.exported));
    const options: [string, string][] = [[models.length ? "最近可用模型" : "暂无同版本模型", "latest"],
      ...models.map(model => [model.label, model.id] as [string, string])];
    if (selected && !options.some(([, id]) => id === selected)) options.push([`已选模型 ${selected.slice(0, 8)}（不可用）`, selected]);
    return options;
  }

  async refresh(): Promise<void> {
    if (this.pending || !agentClient.desktop) return;
    this.pending = true;
    try {
      const result = await agentClient.request<{ models: Model[] }>({ action: "reinforcement_models" });
      this.models = result.models;
      const workspace = this.workspace;
      if (!workspace || workspace.isDragging()) return;
      const blocks = [...workspace.getAllBlocks(false), ...(workspace.getFlyout()?.getWorkspace().getAllBlocks(false) ?? [])];
      for (const block of blocks) {
        if (!["table_policy_onnx_run", "table_policy_onnx_export"].includes(block.type)) continue;
        const field = block.getField("MODEL_ID") as Blockly.FieldDropdown | null;
        if (!field) continue;
        const selected = field.getValue();
        field.setOptions(() => this.options(block.type === "table_policy_onnx_run", selected));
        field.setValue(selected); field.forceRerender();
      }
    } finally { this.pending = false; }
  }

  attach(workspace: Blockly.WorkspaceSvg): () => void {
    this.workspace = workspace;
    workspace.registerButtonCallback("REFRESH_ONNX_MODELS", () => { void this.refresh().catch(() => undefined); });
    void this.refresh().catch(() => undefined);
    const timer = setInterval(() => void this.refresh().catch(() => undefined), 10000);
    return () => { clearInterval(timer); if (this.workspace === workspace) this.workspace = undefined; };
  }
}
export const onnxModelCatalog = new OnnxModelCatalog();

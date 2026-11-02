/** 功能：保存积木与变量，重开窗口后恢复；读写失败时保留可编辑工作区。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
export class WorkspaceStore {
  private readonly key = "xiaoxia.blocks.workspace.v1";
  restore(workspace: Blockly.WorkspaceSvg): boolean {
    try {
      const raw = localStorage.getItem(this.key);
      if (!raw || raw.length > 1000000) return false;
      Blockly.serialization.workspaces.load(JSON.parse(raw), workspace);
      return true;
    } catch { workspace.clear(); return false; }
  }
  save(workspace: Blockly.WorkspaceSvg): void {
    try { localStorage.setItem(this.key, JSON.stringify(Blockly.serialization.workspaces.save(workspace))); }
    catch { /* 浏览器存储不可用时仍可编辑和运行。 */ }
  }
}

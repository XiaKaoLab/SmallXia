/** 功能：为机械臂积木提供仿真和实际发现的串口选项，枚举不打开设备。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { agentClient } from "../chat/AgentClient";

export class ArmTargetCatalog {
  private ports: string[] = [];
  private pending = false;
  private workspace?: Blockly.WorkspaceSvg;

  options(selected?: string | null): [string, string][] {
    const options: [string, string][] = [["仿真", "simulation"], ...this.ports.map(port => [port, `serial:${port}`] as [string, string])];
    if (selected?.startsWith("serial:") && !options.some(([, value]) => value === selected)) {
      options.push([`${selected.slice(7)}（离线）`, selected]);
    }
    return options;
  }

  async refresh(): Promise<void> {
    if (this.pending || !agentClient.desktop) return;
    this.pending = true;
    try {
      const response = await agentClient.request<{ ports: string[] }>({ action: "list_arm_ports" });
      this.ports = response.ports;
      const workspace = this.workspace;
      if (!workspace || workspace.isDragging()) return;
      const blocks = [...workspace.getAllBlocks(false), ...(workspace.getFlyout()?.getWorkspace().getAllBlocks(false) ?? [])];
      for (const block of blocks) {
        if (!["table_hardware_connect", "table_hardware_stop", "table_demo_hardware", "table_set_arm_position", "table_calibrate_arm", "table_map_hardware_arm", "table_qiling_load", "table_sim2real_check"].includes(block.type)) continue;
        const field = block.getField("TARGET") as Blockly.FieldDropdown | null;
        if (!field) continue;
        const selected = field.getValue();
        field.setOptions(() => {
          const options = this.options(selected).filter(([, value]) => ["table_set_arm_position","table_qiling_load"].includes(block.type) || value !== "simulation");
          return options.length ? options : [["未发现串口", "unavailable"]];
        });
        if (selected !== "unavailable") field.setValue(selected); field.forceRerender();
      }
    } finally { this.pending = false; }
  }

  attach(workspace: Blockly.WorkspaceSvg): () => void {
    this.workspace = workspace;
    workspace.registerButtonCallback("REFRESH_ARM_PORTS", () => { void this.refresh().catch(() => undefined); });
    void this.refresh().catch(() => undefined);
    const timer = setInterval(() => void this.refresh().catch(() => undefined), 10000);
    return () => { clearInterval(timer); if (this.workspace === workspace) this.workspace = undefined; };
  }
}
export const armTargetCatalog = new ArmTargetCatalog();

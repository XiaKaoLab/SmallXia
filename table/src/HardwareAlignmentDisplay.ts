/** 功能：显示实机六轴只读角度，管理显示对齐流与停止操作。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { agentClient } from "./chat/AgentClient";
import { jointPreview } from "./JointPreview";
import { JOINTS } from "./blocks/positionBlock";

interface AlignmentState {
  status: string; port: string; error?: string; joint_positions?: Record<string, number>;
  outside_device_calibration?: string[]; applied_joint_positions?: Record<string, number>;
  model_limited?: boolean; limit_reason?: string;
}
export class HardwareAlignmentDisplay {
  positions: Record<string, number> | null = null;
  private session = "";
  private requestId = "";
  private generation = 0;
  private readonly panel = document.createElement("section");
  private readonly status = document.createElement("span");
  private readonly values = document.createElement("div");
  private readonly title = document.createElement("strong");
  private readonly stopButton = document.createElement("button");
  private readonly warning = document.createElement("p");
  private readonly start = (event: Event) => {
    const session = (event as CustomEvent<{ id: string; port: string; mode?: string }>).detail;
    void this.follow(session.id, session.port, session.mode);
  };

  constructor(host: HTMLElement) {
    this.panel.className = "hardware-alignment"; this.panel.hidden = true;
    this.panel.setAttribute("aria-label", "机械臂显示对齐角度");
    const heading = document.createElement("div");
    this.title.textContent = "机械臂 · 显示对齐";
    this.stopButton.textContent = "停止跟随";
    this.stopButton.onclick = () => this.stop();
    heading.append(this.title, this.status, this.stopButton); this.panel.append(heading, this.values, this.warning);
    host.append(this.panel); window.addEventListener("table:alignment-start", this.start);
  }

  private async follow(session: string, port: string, mode = "alignment"): Promise<void> {
    this.stop();
    const generation = ++this.generation;
    this.title.textContent = mode === "mapping" ? "真机 → 仿真" : "机械臂 · 显示对齐";
    this.stopButton.textContent = mode === "mapping" ? "停止映射" : "停止跟随";
    this.session = session; this.panel.hidden = false; this.status.textContent = `${port} · 连接中`;
    this.values.replaceChildren(); this.warning.textContent = mode === "mapping" ? "正在读取实机并加载已保存的显示对齐。" : "请保持实机在积木填写的已知角度，等待记录固定零点。";
    const requestId = crypto.randomUUID(); this.requestId = requestId;
    let mapped = false;
    try {
      await agentClient.alignmentPreview<AlignmentState>(requestId, session, state => {
        if (generation !== this.generation) return;
        this.status.textContent = `${state.port} · ${state.status === "following" ? "只读跟随" : state.status === "failed" ? "连接失败" : state.status === "stopped" ? "已停止" : "连接中"}`;
        if (state.joint_positions && JOINTS.every(([name]) => Number.isFinite(state.joint_positions![name]))) {
          this.positions = state.applied_joint_positions ?? state.joint_positions;
          if (mode === "mapping" && !mapped) {
            jointPreview.confirm(this.positions, jointPreview.revision); mapped = true;
          }
          this.values.replaceChildren(...JOINTS.map(([name, label], index) => {
            const value = document.createElement("span");
            const measured = state.joint_positions![name], applied = this.positions![name];
            value.textContent = `M${index + 1} ${label} ${(measured * 180 / Math.PI).toFixed(1)}°${Math.abs(applied - measured) > .001 ? ` → ${(applied * 180 / Math.PI).toFixed(1)}°` : ""}`;
            return value;
          }));
        }
        const limit = state.model_limited ? `模型已停在边界：${state.limit_reason || "姿态约束"}。角度箭头表示实际显示值。` : "";
        this.warning.textContent = limit + (state.error ?? (state.outside_device_calibration?.length
          ? `设备校准范围异常：${state.outside_device_calibration.join("、")}。仅做显示对齐，不能用于实机控制。`
          : "按已填写参考角度计算固定零点；物理零点和方向尚需人工核对。模型受限位和碰撞约束，不用于实机运动。"));
      });
    } catch (error) {
      if (generation === this.generation) this.warning.textContent = String(error);
    } finally {
      if (generation === this.generation) { this.positions = null; this.session = ""; this.requestId = ""; }
    }
  }

  stop(): void {
    this.generation++;
    if (this.session) void agentClient.request({ action: "alignment_stop", session_id: this.session }).catch(() => undefined);
    if (this.requestId) void agentClient.cancel(this.requestId).catch(() => undefined);
    this.session = ""; this.requestId = ""; this.positions = null; this.panel.hidden = true;
  }

  dispose(): void {
    this.stop(); window.removeEventListener("table:alignment-start", this.start); this.panel.remove();
  }
}

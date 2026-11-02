/** 功能：显示实机六轴只读角度，管理显示对齐流与停止操作。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { agentClient } from "./chat/AgentClient";
import { JOINTS } from "./blocks/positionBlock";

interface AlignmentState {
  status: string; port: string; error?: string; joint_positions?: Record<string, number>;
  outside_device_calibration?: string[];
}
export class HardwareAlignmentDisplay {
  positions: Record<string, number> | null = null;
  private session = "";
  private requestId = "";
  private generation = 0;
  private readonly panel = document.createElement("section");
  private readonly status = document.createElement("span");
  private readonly values = document.createElement("div");
  private readonly warning = document.createElement("p");
  private readonly start = (event: Event) => {
    const session = (event as CustomEvent<{ id: string; port: string }>).detail;
    void this.follow(session.id, session.port);
  };

  constructor(host: HTMLElement) {
    this.panel.className = "hardware-alignment"; this.panel.hidden = true;
    this.panel.setAttribute("aria-label", "机械臂显示对齐角度");
    const heading = document.createElement("div");
    const title = document.createElement("strong"); title.textContent = "机械臂 · 显示对齐";
    const stop = document.createElement("button"); stop.textContent = "停止跟随";
    stop.onclick = () => this.stop();
    heading.append(title, this.status, stop); this.panel.append(heading, this.values, this.warning);
    host.append(this.panel); window.addEventListener("table:alignment-start", this.start);
  }

  private async follow(session: string, port: string): Promise<void> {
    this.stop();
    const generation = ++this.generation;
    this.session = session; this.panel.hidden = false; this.status.textContent = `${port} · 连接中`;
    this.values.replaceChildren(); this.warning.textContent = "请保持实机与当前仿真姿态一致，等待记录参考位置。";
    const requestId = crypto.randomUUID(); this.requestId = requestId;
    try {
      await agentClient.alignmentPreview<AlignmentState>(requestId, session, state => {
        if (generation !== this.generation) return;
        this.status.textContent = `${state.port} · ${state.status === "following" ? "只读跟随" : state.status === "failed" ? "连接失败" : state.status === "stopped" ? "已停止" : "连接中"}`;
        if (state.joint_positions && JOINTS.every(([name]) => Number.isFinite(state.joint_positions![name]))) {
          this.positions = state.joint_positions;
          this.values.replaceChildren(...JOINTS.map(([name, label], index) => {
            const value = document.createElement("span");
            value.textContent = `M${index + 1} ${label} ${(state.joint_positions![name] * 180 / Math.PI).toFixed(1)}°`;
            return value;
          }));
        }
        this.warning.textContent = state.error ?? (state.outside_device_calibration?.length
          ? `设备校准范围异常：${state.outside_device_calibration.join("、")}。仅做显示对齐，不能用于实机控制。`
          : "以手动对齐姿态为参考；模型受限位和碰撞约束。此映射不能用于实机运动。");
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

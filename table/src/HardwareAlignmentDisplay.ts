/** 功能：显示实机六轴角度，管理官方校准逐轴向导、跟随流与停止操作。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { agentClient } from "./chat/AgentClient";
import { jointPreview } from "./JointPreview";
import { JOINTS } from "./blocks/positionBlock";

interface AlignmentState {
  status: string; port: string; error?: string; joint_positions?: Record<string, number>;
  outside_device_calibration?: string[]; applied_joint_positions?: Record<string, number>;
  model_limited?: boolean; limit_reason?: string; instruction?: string;
  calibration_stage?: string; joint_index?: number; active_joint?: string;
  current_tick?: number; range_min?: number; range_max?: number; calibration_source?: string;
  completed_ranges?: Record<string, { range_min: number; range_max: number }>;
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
  private readonly calibrationProgress = document.createElement("p");
  private readonly stepButton = document.createElement("button");
  private stepPending = false;
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
    heading.append(this.title, this.status, this.stopButton); this.stepButton.hidden = true;
    this.calibrationProgress.hidden = true; this.calibrationProgress.setAttribute("aria-live", "polite");
    this.panel.append(heading, this.calibrationProgress, this.values, this.warning, this.stepButton);
    host.append(this.panel); window.addEventListener("table:alignment-start", this.start);
  }

  private async follow(session: string, port: string, mode = "alignment"): Promise<void> {
    this.stop();
    const generation = ++this.generation;
    this.title.textContent = mode === "mapping" ? "真机 → 仿真" : "机械臂 · 显示对齐";
    this.stopButton.textContent = mode === "mapping" ? "停止映射" : "停止跟随";
    this.session = session; this.panel.hidden = false; this.status.textContent = `${port} · 连接中`;
    this.values.replaceChildren(); this.stepButton.hidden = true; this.calibrationProgress.hidden = true; this.stepPending = false;
    this.warning.textContent = "正在读取并核对官方校准；缺失时进入逐轴检查。";
    const requestId = crypto.randomUUID(); this.requestId = requestId;
    let mapped = false;
    try {
      await agentClient.alignmentPreview<AlignmentState>(requestId, session, state => {
        if (generation !== this.generation) return;
        this.status.textContent = `${state.port} · ${state.status === "following" ? "只读跟随" : state.status === "failed" ? "连接失败" : state.status === "stopped" ? "已停止" : "连接中"}`;
        const calibrating = state.status === "waiting_center" || state.status === "checking_range";
        this.stepButton.hidden = !calibrating; this.calibrationProgress.hidden = !calibrating;
        this.title.textContent = calibrating ? "机械臂 · 校准向导" : mode === "mapping" ? "真机 → 仿真" : "机械臂 · 校准跟随";
        if (calibrating) {
          this.positions = null;
          this.calibrationProgress.textContent = state.status === "waiting_center"
            ? "步骤 1：摆放中位 → 步骤 2：逐轴检查 → 步骤 3：保存校准"
            : JOINTS.map(([name, label], index) => `${state.completed_ranges?.[name] ? "✓" : index === state.joint_index ? "▶" : "○"} M${index + 1} ${label}`).join(" · ");
          this.status.textContent = `${state.port} · ${state.status === "waiting_center" ? "等待中位" : `检查 M${(state.joint_index ?? 0) + 1}`}`;
          this.stepButton.textContent = state.status === "waiting_center" ? "记录中位并检查行程" : state.joint_index === 5 ? "确认夹爪范围并保存" : "确认范围 · 下一关节";
          this.stepButton.disabled = this.stepPending;
          this.stepButton.onclick = async () => {
            if (this.stepPending || generation !== this.generation) return;
            this.stepPending = true; this.stepButton.disabled = true;
            try {
              await agentClient.request({ action: "arm_calibration_action", session_id: session,
                stage: state.calibration_stage, index: state.joint_index });
            } catch (error) { if (generation === this.generation) this.warning.textContent = String(error); }
            finally { if (generation === this.generation) { this.stepPending = false; this.stepButton.disabled = false; } }
          };
          this.values.textContent = state.active_joint
            ? `${JOINTS.find(([name]) => name === state.active_joint)?.[1] ?? state.active_joint} · 最小 ${state.range_min} / 当前 ${state.current_tick} / 最大 ${state.range_max} 刻度` : "";
        }
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
        this.warning.textContent = limit + (state.error ?? (calibrating ? state.instruction : undefined) ?? (state.outside_device_calibration?.length
          ? `设备校准范围异常：${state.outside_device_calibration.join("、")}。仅做显示对齐，不能用于实机控制。`
          : "已复用官方校准，编码器计数已转换为模型角度；夹爪为开合比例转换。SO-100 与 SO-101 几何一致性尚需核对。"));
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

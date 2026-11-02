/** 功能：显示实机六轴角度，管理官方校准六轴向导、跟随流与停止操作。
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
  joint_ranges?: Record<string, { current: number; min: number; max: number; mid: number }>;
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
  private readonly savedNotice = document.createElement("div");
  private noticeTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly warning = document.createElement("p");
  private readonly start = (event: Event) => {
    const session = (event as CustomEvent<{ id: string; port: string; mode?: string }>).detail;
    void this.follow(session.id, session.port, session.mode);
  };

  constructor(host: HTMLElement) {
    this.values.className = "alignment-values";
    this.panel.className = "hardware-alignment"; this.panel.hidden = true;
    this.panel.setAttribute("aria-label", "机械臂显示对齐角度");
    const heading = document.createElement("div");
    this.title.textContent = "机械臂 · 显示对齐";
    this.stopButton.textContent = "停止跟随";
    this.stopButton.onclick = () => this.stop();
    heading.append(this.title, this.status, this.stopButton); this.stepButton.hidden = true;
    this.calibrationProgress.hidden = true; this.calibrationProgress.setAttribute("aria-live", "polite");
    this.panel.append(heading, this.calibrationProgress, this.values, this.warning, this.stepButton);
    this.savedNotice.className = "calibration-saved-notice"; this.savedNotice.hidden = true;
    this.savedNotice.setAttribute("role", "status"); this.savedNotice.setAttribute("aria-live", "polite");
    host.append(this.savedNotice);
    host.append(this.panel); window.addEventListener("table:alignment-start", this.start);
  }

  private async follow(session: string, port: string, mode = "alignment"): Promise<void> {
    this.stop();
    clearTimeout(this.noticeTimer); this.savedNotice.hidden = true;
    const generation = ++this.generation;
    this.title.textContent = mode === "mapping" ? "真机 → 仿真" : "机械臂 · 显示对齐";
    this.stopButton.textContent = mode === "mapping" ? "停止映射" : "停止跟随";
    this.session = session; this.panel.hidden = false; this.status.textContent = `${port} · 连接中`;
    this.values.replaceChildren(); this.stepButton.hidden = true; this.calibrationProgress.hidden = true; this.stepPending = false;
    this.warning.hidden = false;
    this.warning.textContent = ""; this.warning.hidden = true;
    const requestId = crypto.randomUUID(); this.requestId = requestId;
    let mapped = false;
    try {
      await agentClient.alignmentPreview<AlignmentState>(requestId, session, state => {
        if (generation !== this.generation) return;
        if (state.status === "saved" || (state.status === "following" && state.calibration_source === "guided_range_check")) {
          this.stop();
          this.savedNotice.textContent = `${state.port} · 校准已保存`;
          this.savedNotice.hidden = false;
          clearTimeout(this.noticeTimer);
          this.noticeTimer = setTimeout(() => { this.savedNotice.hidden = true; }, 4000);
          return;
        }
        this.status.textContent = `${state.port} · ${state.status === "following" ? "只读跟随" : state.status === "failed" ? "连接失败" : state.status === "stopped" ? "已停止" : "连接中"}`;
        const calibrating = state.status === "checking_range";
        this.panel.classList.toggle("is-calibrating", calibrating);
        this.stepButton.hidden = !calibrating; this.calibrationProgress.hidden = !calibrating;
        this.title.textContent = calibrating ? "机械臂 · 校准向导" : mode === "mapping" ? "真机 → 仿真" : "机械臂 · 校准跟随";
        if (calibrating) {
          this.positions = null;
          this.calibrationProgress.textContent = "请转动各个关节";
          this.status.textContent = `${state.port} · 六轴采集中`;
          this.stepButton.textContent = "保存校准";
          this.stepButton.disabled = this.stepPending;
          this.stepButton.onclick = async () => {
            if (this.stepPending || generation !== this.generation) return;
            this.stepPending = true; this.stepButton.disabled = true;
            try {
              await agentClient.request({ action: "arm_calibration_action", session_id: session,
                stage: state.calibration_stage, index: state.joint_index });
            } catch (error) { if (generation === this.generation) { this.warning.hidden = false; this.warning.textContent = String(error); } }
            finally { if (generation === this.generation) { this.stepPending = false; this.stepButton.disabled = false; } }
          };
          this.values.classList.toggle("calibration-joints", !!state.joint_ranges);
          this.values.replaceChildren(...(state.joint_ranges ? JOINTS.map(([name, label], index) => {
            const range = state.joint_ranges![name];
            const row = document.createElement("div"); row.className = "calibration-joint";
            const title = document.createElement("label"); title.textContent = `M${index + 1} ${label}`;
            const track = document.createElement("div"); track.className = "calibration-track";
            const slider = document.createElement("input"); slider.type = "range"; slider.min = "0"; slider.max = "4095";
            slider.value = String(range.current); slider.disabled = true; slider.setAttribute("aria-label", `${label}当前编码器位置`);
            const markers = document.createElement("span"); markers.className = "calibration-extents";
            markers.style.left = `${range.min / 4095 * 100}%`; markers.style.width = `${(range.max - range.min) / 4095 * 100}%`;
            const middle = document.createElement("i"); middle.style.left = `${range.mid / 4095 * 100}%`;
            track.append(markers, middle, slider);
            const angle = document.createElement("output"); angle.textContent = `${((range.current - range.mid) * 360 / 4095).toFixed(1)}°`;
            row.append(title, track, angle); return row;
          }) : []));
        }
        if (!calibrating) this.values.classList.remove("calibration-joints");
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
        this.warning.textContent = limit + (state.error ?? (calibrating ? (state.instruction?.startsWith("以下关节采集行程不足") ? state.instruction : "") : undefined) ?? (state.outside_device_calibration?.length
          ? `设备校准范围异常：${state.outside_device_calibration.join("、")}。仅做显示对齐，不能用于实机控制。`
          : ""));
        this.warning.hidden = !this.warning.textContent;
      });
    } catch (error) {
      if (generation === this.generation) { this.warning.hidden = false; this.warning.textContent = String(error); }
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
    clearTimeout(this.noticeTimer); this.savedNotice.remove();
    this.stop(); window.removeEventListener("table:alignment-start", this.start); this.panel.remove();
  }
}

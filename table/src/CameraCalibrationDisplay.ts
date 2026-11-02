/** 功能：复用桌面流显示真实相机标定预览、采样、内参误差与导出。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { UiMessage } from "./shared/UiMessage";
import { agentClient } from "./chat/AgentClient";

interface CalibrationResult {
  camera_matrix: number[][]; distortion: number[]; rms_px: number;
  per_view_rms_px: number[]; quality: string; warnings: string[]; image_size: number[];
}
interface CalibrationState {
  id: string; camera_id: string; camera_name: string; columns: number; rows: number; square_mm: number;
  samples: number; minimum_samples: number; result: CalibrationResult | null;
  image?: string; board_found?: boolean; error?: string;
}
export class CameraCalibrationDisplay {
  private readonly panel = document.createElement("section");
  private readonly image = document.createElement("img");
  private readonly status = document.createElement("p");
  private readonly message = document.createElement("p");
  private readonly result = document.createElement("pre");
  private readonly capture = document.createElement("button");
  private readonly solve = document.createElement("button");
  private readonly save = document.createElement("button");
  private state?: CalibrationState;
  private busy = false;
  private requestId = "";
  private generation = 0;
  private actionError = "";
  private readonly start = (event: Event) => { void this.open((event as CustomEvent<CalibrationState>).detail); };

  constructor(private readonly host: HTMLElement) {
    this.panel.className = "camera-calibration"; this.panel.hidden = true;
    this.panel.setAttribute("aria-label", "真实相机内参标定");
    const heading = document.createElement("header");
    const title = document.createElement("strong"); title.textContent = "真实相机 · 内参标定";
    const close = this.button("关闭", () => this.close()); heading.append(title, close);
    this.image.alt = "真实相机棋盘格角点预览";
    this.image.width = 640; this.image.height = 480;
    const actions = document.createElement("div"); actions.className = "camera-calibration-actions";
    this.capture.textContent = "采集此帧"; this.capture.onclick = () => { void this.act("capture"); };
    this.solve.textContent = "计算并保存"; this.solve.onclick = () => { void this.act("solve"); };
    this.save.textContent = "导出内参"; this.save.onclick = () => {
      if (this.state?.result) this.download("intrinsics.json", JSON.stringify(this.state.result, null, 2), "application/json");
    };
    actions.append(this.button("下载标定板", () => this.board()), this.capture, this.solve, this.save);
    this.message.setAttribute("role", "status");
    this.panel.append(heading, this.image, this.status, actions, this.message, this.result);
    host.append(this.panel); window.addEventListener("table:camera-calibration-start", this.start);
  }

  private button(label: string, action: () => void): HTMLButtonElement {
    const button = document.createElement("button"); button.type = "button";
    button.textContent = label; button.onclick = action; return button;
  }

  private async open(state: CalibrationState): Promise<void> {
    this.close(); const generation = ++this.generation;
    this.state = state; this.panel.hidden = false; this.host.classList.add("camera-calibrating");
    this.image.removeAttribute("src"); this.actionError = ""; this.update(state);
    this.requestId = crypto.randomUUID();
    try {
      await agentClient.calibrationPreview<CalibrationState>(this.requestId, state.id, next => {
        if (generation === this.generation) this.update(next);
      });
    } catch (error) {
      if (generation === this.generation) { this.actionError = String(error); this.update(this.state!); }
    }
  }

  private update(state: CalibrationState): void {
    this.state = state;
    if (state.image) this.image.src = state.image;
    this.status.textContent = `${state.camera_name} · ${state.samples}/${state.minimum_samples} 帧 · ${state.board_found ? "已识别标定板" : "等待标定板"}`;
    this.capture.disabled = this.busy || !state.board_found || !!state.error;
    this.solve.disabled = this.busy || state.samples < state.minimum_samples;
    this.save.disabled = !state.result;
    const failure = this.actionError || state.error;
    this.message.textContent = failure ? UiMessage.error(failure) : state.result ? "标定已保存" : "请移动标定板并采集";
    const result = state.result;
    this.result.textContent = result ? `误差 ${result.rms_px.toFixed(3)} px · ${result.image_size.join("×")}${result.warnings.length ? `\n${result.warnings.map(value => UiMessage.error(value, "请补充标定样本")).join("；")}` : ""}` : "";
  }

  private async act(operation: "capture" | "solve"): Promise<void> {
    if (!this.state || this.busy) return;
    const generation = this.generation, previous = this.state;
    this.busy = true; this.actionError = ""; this.update(previous);
    try {
      const state = await agentClient.request<CalibrationState>({ action: "camera_calibration_action", operation, session_id: previous.id });
      if (generation === this.generation) this.update({ ...state, image: this.state?.image, board_found: this.state?.board_found });
    } catch (error) {
      if (generation === this.generation) this.actionError = String(error);
    } finally {
      if (generation === this.generation) { this.busy = false; this.update(this.state!); }
    }
  }

  private board(): void {
    const state = this.state; if (!state) return;
    const size = state.square_mm, width = (state.columns + 1) * size + 30, height = (state.rows + 1) * size + 30;
    const squares: string[] = [];
    for (let row = 0; row <= state.rows; row++) for (let col = 0; col <= state.columns; col++) {
      if ((row + col) % 2 === 0) squares.push(`<rect x="${15 + col * size}" y="${15 + row * size}" width="${size}" height="${size}" fill="black"/>`);
    }
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}mm" height="${height}mm" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="white"/>${squares.join("")}</svg>`;
    this.download(`chessboard-${state.columns}x${state.rows}-${size}mm.svg`, svg, "image/svg+xml");
  }

  private download(name: string, content: string, type: string): void {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = document.createElement("a"); link.href = url; link.download = name;
    this.panel.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  close(): void {
    this.generation++;
    if (this.requestId) void agentClient.cancel(this.requestId).catch(() => undefined);
    this.requestId = ""; this.busy = false; this.panel.hidden = true; this.host.classList.remove("camera-calibrating");
  }

  dispose(): void {
    this.close(); window.removeEventListener("table:camera-calibration-start", this.start); this.panel.remove();
  }
}

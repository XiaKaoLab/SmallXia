/** 功能：订阅 core 本机模型目标，仅更新机械臂显示。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import type { VirtualCameraConfig } from "./VirtualCameraRig";

export class ModelMotionClient {
  private readonly controller = new AbortController();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private stopped = false;

  constructor(private readonly apply: (positions: Record<string, number>, camera: VirtualCameraConfig | null) => void) {
    void this.poll();
  }

  private async poll(): Promise<void> {
    let delay = 33;
    try {
      const response = await fetch("http://127.0.0.1:8766/api/v1/robots/table/state", {
        signal: AbortSignal.any([this.controller.signal, AbortSignal.timeout(1000)]),
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`模型状态 HTTP ${response.status}`);
      const state = await response.json();
      if (state.unit !== "rad" || state.physical !== false || state.source !== "display_target") {
        throw new Error("模型运动协议不匹配");
      }
      if (!this.stopped) this.apply(state.joint_positions, state.camera ?? null);
    } catch {
      delay = 1000;
    }
    if (!this.stopped) this.timer = setTimeout(() => void this.poll(), delay);
  }

  dispose(): void {
    this.stopped = true;
    this.controller.abort();
    clearTimeout(this.timer);
  }
}

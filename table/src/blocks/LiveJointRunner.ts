/** 功能：合并滑杆修改，以单请求队列运行最新 Python 位置程序。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { agentClient } from "../chat/AgentClient";

export class LiveJointRunner {
  private pending: string | undefined;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private busy = false;
  private stopped = false;
  private paused = false;
  private idleWaiters: (() => void)[] = [];

  constructor(private readonly status: (message: string) => void) {}

  schedule(source: string): void {
    if (this.stopped) return;
    if (!agentClient.desktop) { this.status("本地预览；API 同步需要 Tauri 桌面"); return; }
    this.pending = source;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.send(), 120);
  }

  private async send(): Promise<void> {
    if (this.stopped || this.paused || this.busy || !this.pending) return;
    const source = this.pending;
    this.pending = undefined;
    this.busy = true;
    try {
      await agentClient.request({ action: "run_program", source });
      if (!this.stopped && !this.pending) this.status("角度已同步到模型 API");
    } catch (error) {
      if (!this.stopped) this.status(`当前为本地预览；API 同步失败：${String(error)}`);
    } finally {
      this.busy = false;
      this.idleWaiters.splice(0).forEach((resolve) => resolve());
      if (this.pending && !this.stopped) void this.send();
    }
  }

  async pause(): Promise<void> {
    this.paused = true;
    clearTimeout(this.timer);
    this.pending = undefined;
    if (this.busy) await new Promise<void>((resolve) => this.idleWaiters.push(resolve));
  }

  resume(): void { this.paused = false; if (this.pending && !this.stopped) void this.send(); }

  dispose(): void { this.stopped = true; this.pending = undefined; clearTimeout(this.timer); }
}

/** 功能：合并滑杆修改，以单请求队列运行最新 Python 位置程序。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { jointPreview } from "../JointPreview";
import { agentClient } from "../chat/AgentClient";

export class LiveJointRunner {
  private pending: { source: string; revision: number } | undefined;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private busy = false;
  private stopped = false;
  private paused = false;
  private idleWaiters: (() => void)[] = [];

  constructor(private readonly status: (message: string) => void) {}

  schedule(source: string): void {
    if (this.stopped) return;
    if (!agentClient.desktop) { this.status("本地预览；API 同步需要 Tauri 桌面"); return; }
    this.pending = { source, revision: jointPreview.revision };
    clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.send(), 120);
  }

  private async send(): Promise<void> {
    if (this.stopped || this.paused || this.busy || !this.pending) return;
    const { source, revision } = this.pending;
    this.pending = undefined;
    this.busy = true;
    try {
      const result = await agentClient.request<{ output: string }>({ action: "run_program", source });
      const receipt = JSON.parse(result.output.trim().split("\n").slice(-1)[0] || "{}");
      if (!this.stopped && receipt.limited && receipt.applied_joint_positions) {
        jointPreview.confirm(receipt.applied_joint_positions, revision);
      }
      if (!this.stopped && !this.pending) this.status(receipt.limited ? "已停在碰撞边界前" : "角度已同步到模型 API");
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

/** 功能：合并仿真滑杆预览请求；真机执行由独立积木程序负责。
 * Created on 2026-11-02; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
import { jointPreview } from "../JointPreview";
import { agentClient } from "../chat/AgentClient";

export class LiveJointRunner {
  private pending: { request: Record<string,unknown>; revision: number } | undefined;
  private hardwarePort="";
  private timer: ReturnType<typeof setTimeout> | undefined;
  private busy = false;
  private stopped = false;
  private paused = false;
  private idleWaiters: (() => void)[] = [];

  constructor(private readonly status: (message: string) => void) {}

  schedule(source: string): void {
    if (this.stopped) return;
    if (!agentClient.desktop) { this.status("本地预览；API 同步需要 Tauri 桌面"); return; }
    this.pending = { request:{action:"run_program",source}, revision: jointPreview.revision };
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {this.timer=undefined;void this.send();}, 120);
  }

  get controllingHardware():boolean {return !!this.hardwarePort;}
  activateHardware(port:string):void {this.hardwarePort=port;}
  releaseHardware():void {
    this.hardwarePort="";
  }
  private async send(): Promise<void> {
    if (this.stopped || this.busy || !this.pending || this.paused) return;
    const { request, revision } = this.pending;
    this.pending = undefined;
    this.busy = true;
    try {
      const result = await agentClient.request<{ output?: string; limited?:boolean }>(request);
      const receipt = JSON.parse((result.output??"").trim().split("\n").slice(-1)[0] || "{}");
      if (!this.stopped && receipt.limited && receipt.applied_joint_positions) {
        jointPreview.confirm(receipt.applied_joint_positions, revision);
      }
      if (!this.stopped && !this.pending) this.status(receipt.limited ? "已到运动边界" : "已同步");
    } catch (error) {
      if (!this.stopped) this.status("同步失败，请重试");
    } finally {
      this.busy = false;
      this.idleWaiters.splice(0).forEach((resolve) => resolve());
      if (this.pending && !this.stopped) void this.send();
    }
  }

  async pause(): Promise<void> {
    this.paused = true;
    clearTimeout(this.timer);this.timer=undefined;
    this.pending = undefined;
    if (this.busy) await new Promise<void>((resolve) => this.idleWaiters.push(resolve));
  }

  resume(): void { this.paused = false; if (this.pending && !this.stopped) void this.send(); }

  dispose(): void { this.releaseHardware();this.stopped = true; this.pending = undefined; clearTimeout(this.timer); }
}

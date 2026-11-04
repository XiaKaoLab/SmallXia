/** 功能：合并滑杆修改，以单请求队列运行最新 Python 位置程序。
 * Created on 2026-11-02; Updated on 2026-11-04
 * @author: https://github.com/Linmoqian
 */
import { jointPreview } from "../JointPreview";
import { agentClient } from "../chat/AgentClient";

export class LiveJointRunner {
  private pending: { request: Record<string,unknown>; revision: number; hardware?: boolean } | undefined;
  private hardwarePort="";
  private hardwareKey="";
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
    this.hardwarePort="";this.hardwareKey="";
    if(this.pending?.hardware){this.pending=undefined;clearTimeout(this.timer);this.timer=undefined;}
  }
  scheduleHardware(port:string,positions:Record<string,number>):void {
    if(this.stopped||this.hardwarePort!==port)return;
    const key=port+JSON.stringify(Object.entries(positions).map(([n,v])=>[n,Math.round(v*4095/(2*Math.PI))]));
    if(key===this.hardwareKey)return;
    this.hardwareKey=key;
    this.pending={request:{action:"hardware_drag",port,positions},revision:jointPreview.revision,hardware:true};
    if(!this.timer)this.timer=setTimeout(()=>{this.timer=undefined;void this.send();},100);
  }

  private async send(): Promise<void> {
    if (this.stopped || this.busy || !this.pending || (this.paused&&!this.pending.hardware)) return;
    const { request, revision, hardware } = this.pending;
    this.pending = undefined;
    this.busy = true;
    try {
      const result = await agentClient.request<{ output?: string; limited?:boolean }>(request);
      const receipt = hardware?result:JSON.parse((result.output??"").trim().split("\n").slice(-1)[0] || "{}");
      if (!this.stopped && receipt.limited && receipt.applied_joint_positions) {
        jointPreview.confirm(receipt.applied_joint_positions, revision);
      }
      if (!this.stopped && !this.pending) this.status(receipt.limited ? "已到运动边界" : "已同步");
    } catch (error) {
      if(hardware)this.hardwareKey="";
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

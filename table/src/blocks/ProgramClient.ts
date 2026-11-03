/** 功能：启动并观察后台积木任务，增量传递回执，刷新后可重新连接或停止。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import type { QiLingReceipt } from "./QiLingBlocks";
import { agentClient } from "../chat/AgentClient";

export interface ProgramJob { id: string; status: string; log_tail?: string; error?: string; created_at_ns?: number; process_exited?: boolean }
export interface ProgramReceipt {
  qiling?: QiLingReceipt;
  workflow?: { stage: string; step?: number; total?: number };
  ball_training?: { kind: string }; camera_calibration?: { id: string }; display_alignment?: { id: string };
  limited?: boolean; applied_joint_positions?: Record<string, number>;
}
export class ProgramClient {
  private current?: string;
  private disposed = false;
  private previousLog = "";
  private pendingLine = "";
  constructor(private readonly notice: (text: string) => void, private readonly receipt: (value: ProgramReceipt) => void) {}
  async start(source: string): Promise<ProgramJob> {
    const job = await agentClient.request<ProgramJob>({ action: "program_request", operation: "start", source });
    this.current = job.id; this.previousLog = "";
    return job;
  }
  async recover(): Promise<ProgramJob | undefined> {
    const { jobs } = await agentClient.request<{ jobs: ProgramJob[] }>({ action: "program_request", operation: "list" });
    const job = jobs.find(row => ["queued", "running"].includes(row.status));
    if (job) { this.current = job.id; this.previousLog = ""; }
    return job;
  }
  async observe(job: ProgramJob): Promise<ProgramJob> {
    while (!this.disposed) {
      const next = await agentClient.request<ProgramJob>({ action: "program_request", operation: "get", id: job.id });
      const log = next.log_tail ?? "";
      const suffix = this.previousLog.slice(-512);
      const index = this.previousLog ? log.indexOf(this.previousLog) : -1;
      const suffixIndex = suffix ? log.indexOf(suffix) : -1;
      const overlap = index >= 0 ? index + this.previousLog.length : suffixIndex >= 0 ? suffixIndex + suffix.length : 0;
      if (log !== this.previousLog) {
        const lines = (this.pendingLine + log.slice(overlap)).split("\n");
        this.pendingLine = lines.pop() ?? "";
        for (const line of lines) {
          try {
            const value = JSON.parse(line) as ProgramReceipt;
            this.receipt(value);
            if (value.workflow) this.notice(`${value.workflow.stage}${value.workflow.step ? ` · ${value.workflow.step}/${value.workflow.total}` : ""}`);
          } catch { /* 普通日志不显示到界面。 */ }
        }
        this.previousLog = log;
      }
      if (!["queued", "running"].includes(next.status) && next.process_exited !== false) {
        this.current = undefined;
        if (next.status === "failed" || next.status === "interrupted") throw new Error(next.error || "程序未完成");
        this.notice(next.status === "succeeded" ? "运行完成" : "已停止");
        return next;
      }
      await new Promise(resolve => setTimeout(resolve, 350));
    }
    return job;
  }
  async stop(): Promise<void> {
    if (this.current) await agentClient.request({ action: "program_request", operation: "stop", id: this.current });
  }
  dispose(): void { this.disposed = true; }
}

/** 功能：通过单个持久 Tauri Channel 订阅各训练环境真实姿态，不依赖面板轮询。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { agentClient } from "./chat/AgentClient";

export interface TrainingSnapshot {
  env_index: number; joint_positions: Record<string, number>; ball_position: number[]; ball_radius: number;
  episode_index?: number; floor_z?: number;
}
export interface TrainingPreview { job_id: string; timestamp_ns: number; snapshots: TrainingSnapshot[]; physical: false }

export class TrainingPreviewClient {
  private stopped = false;
  private requestId = "";
  private timer?: ReturnType<typeof setTimeout>;
  constructor(private readonly receive: (frame: TrainingPreview) => void) { void this.connect(); }

  private async connect(): Promise<void> {
    if (this.stopped || !agentClient.desktop) return;
    this.requestId = crypto.randomUUID();
    try {
      await agentClient.trainingPreview<TrainingPreview>(this.requestId, frame => {
        if (!this.stopped && frame.physical === false && Array.isArray(frame.snapshots) && frame.snapshots.length <= 16) this.receive(frame);
      });
    } catch { /* 桌面重载或流断开时保留最后真实姿态，随后重连。 */ }
    if (!this.stopped) this.timer = setTimeout(() => void this.connect(), 500);
  }

  dispose(): void {
    this.stopped = true; clearTimeout(this.timer);
    if (this.requestId) void agentClient.cancel(this.requestId).catch(() => undefined);
  }
}

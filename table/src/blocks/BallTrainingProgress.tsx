/** 功能：发现小球训练任务并显示真实分数、回合进度和仿真预览。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState } from "react";
import { agentClient } from "../chat/AgentClient";
import "./ball-training.css";

interface TrainingJob {
  id: string; kind: string; status: string; phase?: string; error?: string;
  created_at_ns?: number;
  num_envs?: number; rounds?: number; completed_episodes?: number; total_episodes?: number;
  progress?: number; score?: number | null; current_score?: number; successes?: number;
  snapshot?: { joint_positions: Record<string, number>; ball_position: number[]; ball_radius: number };
}
const phases: Record<string, string> = { queued: "准备启动", initializing: "初始化仿真", collecting: "采集经验", learning: "训练策略", exporting: "导出 ONNX", inferencing: "ONNX 推理",
  completed: "训练完成", succeeded: "训练完成", failed: "训练失败", cancelled: "已停止", interrupted: "训练已中断" };
const active = (job: TrainingJob) => ["queued", "running"].includes(job.status);

export function BallTrainingProgress() {
  const [job, setJob] = useState<TrainingJob>();
  const [error, setError] = useState("");
  const [stopping, setStopping] = useState(false);
  const selected = useRef<TrainingJob | undefined>(undefined);
  const ignored = useRef(new Set<string>());

  useEffect(() => {
    if (!agentClient.desktop) return;
    let stopped = false;
    const mountedAt = Date.now();
    let timer: ReturnType<typeof setTimeout>;
    const onStarted = (event: Event) => {
      const next = (event as CustomEvent<TrainingJob>).detail;
      selected.current = next; setJob(next); setError("");
    };
    window.addEventListener("table:ball-training-started", onStarted);
    async function poll() {
      try {
        const { jobs } = await agentClient.request<{ jobs: TrainingJob[] }>({ action: "reinforcement_jobs" });
        if (stopped) return;
        const candidates = jobs.filter(item => ["ball_pickup", "ball_onnx_rollout"].includes(item.kind) && !ignored.current.has(item.id));
        const next = candidates.find(active) ?? candidates.find(item => item.id === selected.current?.id)
          ?? candidates.filter(item => (item.created_at_ns ?? 0) / 1000000 >= mountedAt)
            .sort((first, second) => (second.created_at_ns ?? 0) - (first.created_at_ns ?? 0))[0];
        if (next) {
          selected.current = next; setJob(next); setError("");
          if (next.snapshot) window.dispatchEvent(new CustomEvent("table:ball-training", { detail: next.snapshot }));
        }
      } catch (failure) { if (!stopped && selected.current) setError(`进度连接中断：${String(failure)}`); }
      finally { if (!stopped) timer = setTimeout(() => void poll(), 1500); }
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); window.removeEventListener("table:ball-training-started", onStarted); window.dispatchEvent(new CustomEvent("table:ball-training", { detail: null })); };
  }, []);

  async function stop() {
    if (!job || stopping) return;
    setStopping(true);
    try {
      const result = await agentClient.request<TrainingJob>({ action: "reinforcement_stop", job_id: job.id });
      selected.current = result; setJob(result); setError("");
    } catch (failure) { setError(String(failure)); }
    finally { setStopping(false); }
  }

  if (!job) return null;
  const running = active(job);
  const progress = Math.max(0, Math.min(1, job.progress ?? 0));
  return <section className="ball-training" aria-label="拿取小球训练进度">
    <div className="ball-training-heading"><strong>{job.kind === "ball_onnx_rollout" ? "拿取小球 · ONNX" : "拿取小球"}</strong><span role="status">{!running && job.status === "succeeded" && job.kind === "ball_onnx_rollout" ? "推理完成" : phases[running ? job.phase ?? job.status : job.status] ?? "运行中"}</span>
      {running ? <button type="button" onClick={() => void stop()} disabled={stopping}>{stopping ? "停止中" : "停止"}</button>
        : <button type="button" aria-label="关闭训练进度" onClick={() => { ignored.current.add(job.id); selected.current = undefined; setJob(undefined); window.dispatchEvent(new CustomEvent("table:ball-training", { detail: null })); }}>关闭</button>}
    </div>
    <div className="ball-training-scores"><span>平均分 <b>{job.score == null ? "—" : job.score.toFixed(2)}</b></span>
      <span>当前分 <b>{job.current_score == null ? "—" : job.current_score.toFixed(2)}</b></span></div>
    <progress max={1} value={progress} aria-label="训练完成进度" />
    <div className="ball-training-detail"><span>{job.completed_episodes ?? 0} / {job.total_episodes ?? "—"} 回合</span><span>{(progress * 100).toFixed(1)}%</span></div>
    <p>{job.num_envs ?? "—"} 个环境 · 每个 {job.rounds ?? "—"} 轮 · 成功 {job.successes ?? 0} 次</p>
    <small>平均分为最近 100 个已完成回合的累计奖励；画面为环境 1。</small>
    {(error || job.error) && <p role="alert" className="ball-training-error">{error || job.error}</p>}
  </section>;
}

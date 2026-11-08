/** 功能：暂存滑杆的即时模型姿态，防止旧 API 轮询覆盖尚未同步的目标。
 * Created on 2026-11-02; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
class JointPreview {
  revision = 0;
  displayed: Record<string, number> = {};
  private overrides: Record<string, number> = {};
  private poseListeners = new Set<(positions: Record<string, number>) => Record<string, number>>();
  private listeners = new Set<(name: string, angle: number) => number>();

  stage(name: string, angle: number): number {
    let accepted = angle;
    this.listeners.forEach((listener) => { accepted = listener(name, accepted); });
    this.revision++;
    this.overrides[name] = accepted;
    return accepted;
  }

  stagePose(positions: Record<string, number>): Record<string, number> {
    let accepted = { ...positions };
    this.poseListeners.forEach(listener => { accepted = listener(accepted); });
    this.revision++;
    this.overrides = { ...accepted };
    return accepted;
  }

  subscribePose(listener: (positions: Record<string, number>) => Record<string, number>): () => void {
    this.poseListeners.add(listener);
    return () => { this.poseListeners.delete(listener); };
  }

  confirm(positions: Record<string, number>, revision: number): void {
    if (revision !== this.revision) return;
    this.overrides = {};
    window.dispatchEvent(new CustomEvent("table:joint-confirmed", { detail: positions }));
  }

  reconcile(positions: Record<string, number>): Record<string, number> {
    for (const [name, angle] of Object.entries(this.overrides)) {
      if (Number.isFinite(positions[name]) && Math.abs(positions[name] - angle) < 1e-6) delete this.overrides[name];
    }
    return { ...positions, ...this.overrides };
  }

  subscribe(listener: (name: string, angle: number) => number): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }
}

export const jointPreview = new JointPreview();

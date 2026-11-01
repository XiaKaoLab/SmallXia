/** 功能：暂存滑杆的即时模型姿态，防止旧 API 轮询覆盖尚未同步的目标。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
class JointPreview {
  private overrides: Record<string, number> = {};
  private listeners = new Set<(name: string, angle: number) => void>();

  stage(name: string, angle: number): void {
    this.overrides[name] = angle;
    this.listeners.forEach((listener) => listener(name, angle));
  }

  reconcile(positions: Record<string, number>): Record<string, number> {
    for (const [name, angle] of Object.entries(this.overrides)) {
      if (Number.isFinite(positions[name]) && Math.abs(positions[name] - angle) < 1e-6) delete this.overrides[name];
    }
    return { ...positions, ...this.overrides };
  }

  subscribe(listener: (name: string, angle: number) => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }
}

export const jointPreview = new JointPreview();

/** 功能：管理两侧栏宽度、窗口收缩约束和本机持久化。
 * Created on 2026-11-08; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
export type SidebarSide = "left" | "right";
export interface SidebarSizes { left: number; right: number }

export class SidebarWidths {
  static readonly key = "xiaoxia.sidebar-widths";
  static readonly min = { left: 280, right: 260 };
  static readonly viewerMin = 280;

  defaults(total: number): SidebarSizes {
    return total <= 1100 ? { left: 300, right: 275 } : { left: total / 4, right: total / 4 };
  }
  load(total: number): SidebarSizes {
    try {
      const value = JSON.parse(localStorage.getItem(SidebarWidths.key) || "null");
      if (value && [value.left, value.right].every(n => typeof n === "number" && Number.isFinite(n))) return this.fit(value, total);
    } catch { /* 不可用或损坏时使用默认布局。 */ }
    return this.fit(this.defaults(total), total);
  }
  max(side: SidebarSide, sizes: SidebarSizes, total: number): number {
    const other = side === "left" ? "right" : "left";
    return Math.max(SidebarWidths.min[side], Math.min(720, total - SidebarWidths.viewerMin - sizes[other]));
  }
  resize(side: SidebarSide, width: number, sizes: SidebarSizes, total: number): SidebarSizes {
    return { ...sizes, [side]: Math.max(SidebarWidths.min[side], Math.min(this.max(side, sizes, total), width)) };
  }
  fit(sizes: SidebarSizes, total: number): SidebarSizes {
    if (total <= 760) return sizes;
    const available = total - SidebarWidths.viewerMin;
    let left = Math.max(SidebarWidths.min.left, Math.min(720, sizes.left));
    let right = Math.max(SidebarWidths.min.right, Math.min(720, sizes.right));
    if (left + right > available) {
      const extra = left + right - SidebarWidths.min.left - SidebarWidths.min.right;
      const keep = Math.max(0, available - SidebarWidths.min.left - SidebarWidths.min.right);
      left = SidebarWidths.min.left + (extra ? (left - SidebarWidths.min.left) * keep / extra : 0);
      right = SidebarWidths.min.right + (extra ? (right - SidebarWidths.min.right) * keep / extra : 0);
    }
    return { left, right };
  }
  save(sizes: SidebarSizes): void {
    try { localStorage.setItem(SidebarWidths.key, JSON.stringify(sizes)); } catch { /* 本次拖动仍有效。 */ }
  }
}

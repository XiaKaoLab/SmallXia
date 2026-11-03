/** 功能：展示 Agent 工具操作的虚拟鼠标；动画不发送输入事件，积木桥协调执行时序。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import "./agent-cursor.css";
import { ToolPresentation } from "../chat/ToolPresentation";

export interface CursorPoint { x: number; y: number }

export class AgentCursor {
  private element?: HTMLDivElement;
  private owner = "";
  private timer?: ReturnType<typeof setTimeout>;
  private revision = 0;

  private view(): HTMLDivElement {
    if (!this.element) {
      const element = document.createElement("div");
      element.className = "agent-cursor";
      element.setAttribute("aria-hidden", "true");
      element.innerHTML = '<svg width="27" height="33" viewBox="0 0 27 33"><path d="M3 2L23 19L14 20L10 29Z" fill="white" stroke="#347565" stroke-width="2" stroke-linejoin="round"/></svg><span class="agent-cursor-label"></span><i class="agent-cursor-ring"></i>';
      document.body.append(element);
      this.element = element;
    }
    return this.element;
  }

  begin(owner: string, label: string, point?: CursorPoint): void {
    clearTimeout(this.timer);
    this.owner = owner;
    this.revision++;
    const element = this.view();
    element.classList.remove("is-failed", "is-dragging");
    element.classList.add("is-visible", "is-working");
    element.querySelector("span")!.textContent = label;
    if (point) this.move(owner, point);
  }

  move(owner: string, point: CursorPoint, dragging = false): void {
    if (this.owner !== owner || !Number.isFinite(point.x) || !Number.isFinite(point.y)) return;
    const element = this.view();
    const x = Math.max(8, Math.min(innerWidth - 28, point.x));
    const y = Math.max(8, Math.min(innerHeight - 40, point.y));
    element.style.transform = `translate3d(${x}px, ${y}px, 0)`;
    element.classList.toggle("label-left", x > innerWidth - 210);
    element.classList.toggle("is-dragging", dragging);
  }

  click(owner: string): void {
    if (this.owner !== owner) return;
    const ring = this.view().querySelector("i")!;
    ring.getAnimations().forEach(animation => animation.cancel());
    ring.animate([{ opacity: 0.8, transform: "scale(.3)" }, { opacity: 0, transform: "scale(1.8)" }],
      { duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 80 : 480 });
  }

  finish(owner: string, failed = false): void {
    if (this.owner !== owner) return;
    this.view().classList.toggle("is-failed", failed);
    this.view().classList.remove("is-dragging", "is-working");
    if (failed) this.view().querySelector("span")!.textContent = "这一步没完成";
    const revision = this.revision;
    this.timer = setTimeout(() => {
      if (revision === this.revision) this.hide(owner);
    }, 1200);
  }

  hide(owner: string): void {
    if (this.owner !== owner) return;
    clearTimeout(this.timer);
    this.revision++;
    this.element?.classList.remove("is-visible");
    this.owner = "";
  }

  toolStarted(id: string, name: string): void {
    if (name.startsWith("blocks_") && !["blocks_program_status", "blocks_programs", "blocks_program_stop", "blocks_command_status"].includes(name)) return;
    const owner = `tool:${id}`;
    this.begin(owner, ToolPresentation.describe(name)[0]);
    requestAnimationFrame(() => {
      const card = Array.from(document.querySelectorAll<HTMLElement>("[data-tool-call-id]"))
        .find(element => element.dataset.toolCallId === id);
      const scene = name.startsWith("table_") ? document.querySelector("canvas") : null;
      const rect = (scene ?? card ?? document.querySelector(".chat-sidebar"))?.getBoundingClientRect();
      this.move(owner, rect ? { x: rect.left + 24, y: rect.top + 22 } : { x: innerWidth - 90, y: 100 });
      // 查询是观察而非点击控制按钮；修改和运行动作才显示点击。
      if (ToolPresentation.category(name) !== "查询") this.click(owner);
    });
  }
}

export const agentCursor = new AgentCursor();

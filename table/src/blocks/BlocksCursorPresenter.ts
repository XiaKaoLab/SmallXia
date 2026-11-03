/** 功能：把 MCP 积木操作映射为虚拟鼠标的点击和拖动动画。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { agentCursor } from "../interaction/AgentCursor";
import { blocksDebug } from "../debug/BlocksDebug";

interface VisualCommand { id: string; operation: string; arguments: Record<string, unknown> }
const labels: Record<string, string> = { catalog: "查看积木", list: "查看工作区", create: "添加积木", set_fields: "设置字段",
  move: "移动积木", connect: "连接积木", remove: "删除积木", clear: "清空工作区", export: "读取工作区", import: "导入积木", run: "运行程序" };

export class BlocksCursorPresenter {
  private owner = "";
  private timer?: ReturnType<typeof setTimeout>;
  private frame = 0;

  async begin(command: VisualCommand): Promise<void> {
    this.stop();
    this.owner = `blocks:${command.id}`;
    const args = command.arguments;
    const id = args.child_id ?? args.id;
    if (id) blocksDebug.reveal(String(id), Object.keys(args.fields ?? {})[0]);
    const button = command.operation === "run" ? document.querySelector(".blocks-run")?.getBoundingClientRect() : undefined;
    const target = button ? { x: button.left + button.width / 2, y: button.top + button.height / 2 }
      : blocksDebug.visualTarget(id ? String(id) : undefined, Object.keys(args.fields ?? {})[0]);
    agentCursor.begin(this.owner, labels[command.operation] ?? "操作积木", target);
    await new Promise(resolve => setTimeout(resolve, matchMedia("(prefers-reduced-motion: reduce)").matches ? 20 : 280));
    if (!["catalog", "list", "export"].includes(command.operation)) agentCursor.click(this.owner);
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  complete(command: VisualCommand, result: unknown, failed: boolean): void {
    const owner = this.owner;
    if (!owner) return;
    // 先保留起点一帧，再跟随实际结果移动，最后结束等待反馈。
    this.frame = requestAnimationFrame(() => {
      this.timer = setTimeout(() => {
        if (this.owner !== owner) return;
        const args = command.arguments;
        const created = result && typeof result === "object" && "id" in result ? String(result.id) : undefined;
        const id = created ?? (args.child_id ? String(args.child_id) : args.id ? String(args.id) : undefined);
        if (!failed && ["create", "move", "connect", "set_fields"].includes(command.operation)) {
          if (id) blocksDebug.reveal(id, Object.keys(args.fields ?? {})[0]);
          const point = blocksDebug.visualTarget(id, Object.keys(args.fields ?? {})[0]);
          if (point) agentCursor.move(owner, point, ["move", "connect", "create"].includes(command.operation));
        }
        this.timer = setTimeout(() => agentCursor.finish(owner, failed), 260);
      }, 60);
    });
  }

  stop(): void {
    cancelAnimationFrame(this.frame);
    clearTimeout(this.timer);
    if (this.owner) agentCursor.hide(this.owner);
    this.owner = "";
  }
}

/** 功能：通过受限命令桥将 MCP 积木操作投递到当前 WebView 并确认实际结果。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { agentClient } from "../chat/AgentClient";
import { blocksDebug } from "../debug/BlocksDebug";
import { BlocksCursorPresenter } from "./BlocksCursorPresenter";

interface Command { id: string; operation: string; arguments: Record<string, unknown>; expires_at_ms: number }
export class BlocksControlBridge {
  private stopped = false;
  private readonly cursor = new BlocksCursorPresenter();
  private readonly clientId = crypto.randomUUID().replace(/-/g, "");
  constructor(private readonly run: () => Promise<unknown>, private readonly busy: () => boolean) {}

  private async execute(command: Command): Promise<unknown> {
    if (Date.now() > command.expires_at_ms) throw new Error("积木命令已过期，未执行");
    const args = command.arguments;
    if (this.busy() && !["catalog", "list", "export"].includes(command.operation)) throw new Error("程序运行中，请结束后再修改积木");
    switch (command.operation) {
      case "catalog": return blocksDebug.catalog();
      case "list": return { blocks: blocksDebug.list() };
      case "create": return blocksDebug.create(args.fields as Record<string, string | number> ?? {}, Number(args.x ?? 16), Number(args.y ?? 24), String(args.type));
      case "set_fields": return blocksDebug.setFields(String(args.id), args.fields as Record<string, string | number>);
      case "move": return blocksDebug.move(String(args.id), Number(args.x), Number(args.y));
      case "connect": return { blocks: blocksDebug.connect(String(args.parent_id), String(args.child_id), String(args.input_name ?? "")) };
      case "remove": blocksDebug.remove(String(args.id)); return { blocks: blocksDebug.list() };
      case "clear": blocksDebug.clear(); return { blocks: [] };
      case "export": return blocksDebug.exportWorkspace();
      case "import": return blocksDebug.importWorkspace(args.snapshot);
      case "run": return await this.run();
      default: throw new Error("未知积木操作");
    }
  }

  async start(): Promise<void> {
    if (!agentClient.desktop) return;
    while (!this.stopped) {
      try {
        const { command } = await agentClient.request<{ command: Command | null }>({ action: "blocks_poll", client_id: this.clientId });
        if (!command) continue;
        let result: unknown = null, error: string | undefined;
        try {
          if (this.stopped) throw new Error("工作区已关闭，未执行命令");
          await this.cursor.begin(command);
          if (this.stopped) throw new Error("工作区已关闭，未执行命令");
          result = await this.execute(command);
        } catch (failure) { error = String(failure); }
        if (!this.stopped) {
          this.cursor.complete(command, result, error !== undefined);
          await new Promise(resolve => setTimeout(resolve, matchMedia("(prefers-reduced-motion: reduce)").matches ? 20 : 420));
        }
        await agentClient.request({ action: "blocks_reply", client_id: this.clientId, command_id: command.id,
          ok: error === undefined, result, error });
      } catch { if (!this.stopped) await new Promise(resolve => setTimeout(resolve, 1000)); }
    }
  }

  stop(): void { this.stopped = true; this.cursor.stop(); }
}

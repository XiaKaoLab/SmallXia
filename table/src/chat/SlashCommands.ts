/** 功能：定义聊天斜杠菜单及本地筛选规则。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { BrainCircuit, Minimize2 } from "lucide-react";

export class SlashCommands {
  static readonly items = [
    { name: "压缩", icon: Minimize2, description: "整理当前对话，保留目标和进度" },
    { name: "训练", icon: BrainCircuit, description: "启动仿真训练，可补充任务要求" },
  ];

  static match(value: string) {
    if (!/^\/[^\s]*$/.test(value)) return [];
    const query = value.slice(1);
    return this.items.filter(item => item.name.startsWith(query));
  }

  static selected(value: string) {
    const match = value.match(/^\/([^\s]+)\s([\s\S]*)$/);
    const command = match && this.items.find(item => item.name === match[1]);
    return command ? { command, text: match![2] } : null;
  }
}

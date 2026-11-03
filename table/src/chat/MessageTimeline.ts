/** 功能：按事件到达顺序追加文字和操作，操作完成时只更新原位置。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import type { Activity, ChatMessage, MessagePart } from "./types";

type DisplayGroup = { type: "text"; id: string; text: string } | { type: "activities"; id: string; activities: Activity[] };
export class MessageTimeline {
  static text(message: ChatMessage, delta: string): ChatMessage {
    if (!delta) return message;
    const parts: MessagePart[] = [...(message.parts ?? [])];
    const last = parts[parts.length - 1];
    if (last?.type === "text") parts[parts.length - 1] = { ...last, text: last.text + delta };
    else parts.push({ type: "text", id: `text-${parts.length}`, text: delta });
    return { ...message, content: message.content + delta, parts };
  }
  static activity(message: ChatMessage, activity: Activity): ChatMessage {
    if (message.activities.some(item => item.id === activity.id)) return message;
    return { ...message, activities: [...message.activities, activity], parts: [...(message.parts ?? []), { type: "activity", id: activity.id }] };
  }
  static groups(message: ChatMessage): DisplayGroup[] {
    const parts = message.parts ?? [
      ...message.activities.map(item => ({ type: "activity" as const, id: item.id })),
      ...(message.content ? [{ type: "text" as const, id: "text-legacy", text: message.content }] : []),
    ];
    const groups: DisplayGroup[] = [];
    const activities = new Map(message.activities.map(item => [item.id, item]));
    for (const part of parts) {
      if (part.type === "text") { groups.push(part); continue; }
      const activity = activities.get(part.id);
      if (!activity) continue;
      const last = groups[groups.length - 1];
      if (last?.type === "activities") last.activities.push(activity);
      else groups.push({ type: "activities", id: part.id, activities: [activity] });
    }
    return groups;
  }
}

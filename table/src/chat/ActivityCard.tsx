/** 功能：渲染可展开的技能和工具执行活动卡片。
 * Created on 2026-11-01; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { Check, ChevronRight, CircleAlert, LoaderCircle, Square, Search, Pencil, Play, WandSparkles } from "lucide-react";
import type { Activity } from "./types";
import { ToolPresentation } from "./ToolPresentation";
import { ToolResult } from "./ToolResult";

export function ActivityCard({ activity }: { activity: Activity }) {
  const Status = activity.status === "running" ? LoaderCircle : activity.status === "failed" ? CircleAlert : activity.status === "cancelled" ? Square : Check;
  const [title, description] = activity.kind === "skill" ? [activity.name, "使用技能"] : ToolPresentation.describe(activity.name);
  const category = ToolPresentation.category(activity.name);
  const ActionIcon = category === "查询" ? Search : category === "修改" ? Pencil : Play;
  return <details className={`activity-card activity-${activity.status}`} data-tool-call-id={activity.kind === "tool" ? activity.id : undefined}>
    <summary title={description}>
      {activity.kind === "skill" ? <WandSparkles size={14} /> : <ActionIcon size={14} />}
      <span><strong>{activity.kind === "skill" ? title : category}</strong><small>{activity.kind === "skill" ? description : title}</small></span>
      <Status size={13} className={activity.status === "running" ? "spin" : ""} />
      <ChevronRight size={13} className="activity-chevron" />
    </summary>
    {activity.output ? <ToolResult name={activity.name} output={activity.output} /> : <p className="tool-result-empty">{activity.status === "running" ? "正在执行…" : "暂无输出"}</p>}
  </details>;
}

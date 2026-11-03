/** 功能：按时间线交错显示流式文字与操作卡片，连续操作保持可滚动堆栈。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ActivityCard } from "./ActivityCard";
import { MessageTimeline } from "./MessageTimeline";
import type { ChatMessage } from "./types";

export function MessageBody({ message }: { message: ChatMessage }) {
  const groups = MessageTimeline.groups(message);
  return <>{groups.map(group => group.type === "activities"
    ? <div key={group.id} className="activity-stack" aria-label="技能与工具活动" tabIndex={0}>{group.activities.map(activity => <ActivityCard key={activity.id} activity={activity} />)}</div>
    : <div key={group.id} className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: ({ children, href, title }) => <a href={href} title={title} target="_blank" rel="noreferrer">{children}</a> }}>{group.text}</ReactMarkdown></div>)}
    {message.status === "streaming" && !message.content && !message.activities.some(item => item.status === "running") && <div className="thinking" role="status" aria-label="正在生成"><i /><i /><i /></div>}
    {message.status === "streaming" && groups[groups.length - 1]?.type === "text" && <span className="stream-caret" />}
  </>;
}

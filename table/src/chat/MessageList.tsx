/** 功能：聊天气泡、Markdown、活动堆栈与流式滚动。
 * Created on 2026-11-01; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { ArrowDown, Check, Copy } from "lucide-react";
import { IconButton } from "../shared/IconButton";
import { MessageBody } from "./MessageBody";
import type { ChatMessage } from "./types";

function CopyMessage({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  useEffect(() => { if (state === "idle") return; const timer = setTimeout(() => setState("idle"), 1800); return () => clearTimeout(timer); }, [state]);
  return <span className="copy-action"><IconButton label={state === "copied" ? "已复制" : "复制回复"} onClick={() => {
    void navigator.clipboard.writeText(text).then(() => setState("copied")).catch(() => setState("failed"));
  }}>{state === "copied" ? <Check size={14} /> : <Copy size={14} />}</IconButton>
    {state === "failed" && <small role="status">复制失败</small>}</span>;
}

export function MessageList({ messages, busy }: { messages: ChatMessage[]; busy: boolean }) {
  const scroll = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [showBottom, setShowBottom] = useState(false);
  useEffect(() => {
    if (pinned.current && scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [messages]);

  return <div className="conversation-shell">
    <div ref={scroll} className="conversation-scroll" role="log" aria-label="聊天消息" aria-live="off" tabIndex={0} onScroll={() => {
      const element = scroll.current;
      if (!element) return;
      pinned.current = element.scrollHeight - element.scrollTop - element.clientHeight < 72;
      setShowBottom(!pinned.current);
    }}>
      {messages.length > 0 && <div className="message-list">
        {messages.map((message) => <motion.article key={message.id} className={`message message-${message.role}`} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.16 }}>
          {message.role === "user" ? <div className="user-bubble">{message.content}</div> : <>
            <MessageBody message={message} />
            {message.status === "completed" && <div className="message-actions"><CopyMessage text={message.content} />{message.result?.output_tokens != null && <small>{message.result.output_tokens} tokens</small>}</div>}
            {(message.status === "failed" || message.status === "cancelled") && <small className="message-interrupted">{message.status === "cancelled" ? "已停止生成" : "回答未完成"}</small>}
          </>}
        </motion.article>)}
      </div>}
    </div>
    {showBottom && <IconButton label="回到最新消息" className="scroll-bottom" onClick={() => {
      pinned.current = true; setShowBottom(false);
      if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight;
    }}><ArrowDown size={16} /></IconButton>}
    <span className="sr-only" role="status">{busy ? "小虾正在生成回复" : "可以发送消息"}</span>
  </div>;
}

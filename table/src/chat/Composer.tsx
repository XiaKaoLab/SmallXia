/** 功能：自适应消息输入框、中文输入保护与发送/停止交互。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import { useLayoutEffect, useRef } from "react";
import { ArrowUp, Square, WandSparkles } from "lucide-react";

interface Props {
  value: string; onChange: (value: string) => void; onSend: () => void; onStop: () => void;
  busy: boolean; disabled: boolean; skillCount: number; onSkills: () => void;
}

export function Composer({ value, onChange, onSend, onStop, busy, disabled, skillCount, onSkills }: Props) {
  const input = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 150)}px`;
  }, [value]);
  return <form className="composer" onSubmit={(event) => { event.preventDefault(); if (!busy && !disabled && value.trim()) onSend(); }}>
    <textarea id="chat-message-input" ref={input} value={value} rows={1} aria-label="发送消息给小虾" placeholder="有什么想法？" onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
        event.preventDefault();
        if (!busy && !disabled && value.trim()) onSend();
      }
    }} />
    <div className="composer-tools">
      <button type="button" className={`skill-trigger ${skillCount ? "is-selected" : ""}`} onClick={onSkills} disabled={busy} aria-label="选择技能"><WandSparkles size={15} /><span>技能{skillCount ? ` ${skillCount}` : ""}</span></button>
      <span className="composer-hint">Shift ↵ 换行</span>
      {busy ? <button type="button" className="send-button" aria-label="停止生成" onClick={onStop}><Square size={13} fill="currentColor" /></button> : <button type="submit" className="send-button" aria-label="发送消息" disabled={disabled || !value.trim()}><ArrowUp size={18} /></button>}
    </div>
  </form>;
}

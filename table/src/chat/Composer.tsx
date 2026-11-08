/** 功能：自适应消息输入框、中文输入保护与发送/停止交互。
 * Created on 2026-11-01; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { ArrowUp, Square, X } from "lucide-react";
import { SlashCommands } from "./SlashCommands";
import { ChatTargetSelect } from "./ChatTargetSelect";

interface Props {
  value: string; onChange: (value: string) => void; onSend: () => void; onStop: () => void;
  busy: boolean; disabled: boolean;
  target: string; onTargetChange: (target: string) => void;
}

export function Composer({ value, onChange, onSend, onStop, busy, disabled, target, onTargetChange }: Props) {
  const input = useRef<HTMLTextAreaElement>(null);
  const composing = useRef(false);
  const menuId = useId();
  const [selected, setSelected] = useState(0);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const activeCommand = SlashCommands.selected(value);
  const visibleValue = activeCommand?.text ?? value;
  const commands = !busy && !disabled && dismissed !== value ? SlashCommands.match(value) : [];
  const choice = Math.min(selected, Math.max(0, commands.length - 1));
  useEffect(() => { setSelected(0); }, [value]);
  const choose = (name: string) => {
    onChange(`/${name} `);
    requestAnimationFrame(() => input.current?.focus());
  };
  useLayoutEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 150)}px`;
  }, [value]);
  return <form className="composer" onSubmit={(event) => {
    event.preventDefault();
    if (commands.length) { choose(commands[choice].name); return; }
    if (!busy && !disabled && value.trim() && value.trim() !== "/") onSend();
  }}>
    {commands.length > 0 && <div id={menuId} className="slash-menu" role="listbox" aria-label="快捷命令">
      {commands.map((command, index) => <button key={command.name} id={`${menuId}-${index}`} type="button" role="option"
        title={command.description} aria-label={command.name}
        aria-selected={index === choice} className={`menu-row ${index === choice ? "selected" : ""}`}
        onMouseEnter={() => setSelected(index)} onMouseDown={event => event.preventDefault()} onClick={() => choose(command.name)}>
        <command.icon size={17} className="slash-command-icon" aria-hidden="true" /><span className="slash-command-name">{command.name}</span>
      </button>)}
    </div>}
    <div className="composer-input-row">
    {activeCommand && <span className="composer-command">
      <activeCommand.command.icon size={15} aria-hidden="true" /><span>{activeCommand.command.name}</span>
      <button type="button" aria-label={`移除${activeCommand.command.name}命令`} title="移除命令" onClick={() => {
        onChange(activeCommand.text); input.current?.focus();
      }}><X size={12} /></button>
    </span>}
    <textarea id="chat-message-input" ref={input} value={visibleValue} rows={1} aria-label="发送消息给小虾" placeholder={activeCommand ? "" : "有什么想法？"} onChange={(event) => onChange(activeCommand ? `/${activeCommand.command.name} ${event.target.value}` : event.target.value)}
      role="combobox" aria-autocomplete="list" aria-haspopup="listbox" aria-expanded={commands.length > 0}
      aria-controls={commands.length ? menuId : undefined} aria-activedescendant={commands.length ? `${menuId}-${choice}` : undefined}
      onCompositionStart={() => { composing.current = true; }} onCompositionEnd={() => { composing.current = false; }} onKeyDown={(event) => {
      if (composing.current || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return;
      if (activeCommand && event.key === "Backspace" && event.currentTarget.selectionStart === 0 && event.currentTarget.selectionEnd === 0) {
        event.preventDefault(); onChange(activeCommand.text); return;
      }
      if (commands.length) {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          setSelected((choice + (event.key === "ArrowDown" ? 1 : commands.length - 1)) % commands.length);
          return;
        }
        if (event.key === "Escape") { event.preventDefault(); setDismissed(value); return; }
        if (event.key === "Tab" || (event.key === "Enter" && !event.shiftKey)) {
          event.preventDefault(); if (!event.repeat) choose(commands[choice].name); return;
        }
      }
      if (event.key === "Enter" && !event.shiftKey && !composing.current && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) {
        event.preventDefault();
        if (!event.repeat && !busy && !disabled && value.trim()) event.currentTarget.form?.requestSubmit();
      }
    }} />
    </div>
    <div className="composer-tools">
      <ChatTargetSelect value={target} onChange={onTargetChange} disabled={busy || disabled} />
      {busy ? <button type="button" className="send-button" aria-label="停止生成" onClick={onStop}><Square size={13} fill="currentColor" /></button> : <button type="submit" className="send-button" aria-label="发送消息" disabled={disabled || !value.trim()}><ArrowUp size={18} /></button>}
    </div>
  </form>;
}

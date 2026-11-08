/** 功能：输入框内选择本轮机械臂目标，枚举串口但不连接或使能。
 * Created on 2026-11-08; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useId, useRef, useState } from "react";
import { Box, Check, ChevronDown, Cpu } from "lucide-react";
import { agentClient } from "./AgentClient";

export function ChatTargetSelect({ value, onChange, disabled }: { value: string; onChange: (value: string) => void; disabled: boolean }) {
  const [ports, setPorts] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const host = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!host.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  useEffect(() => {
    let disposed = false;
    const refresh = async () => {
      if (!agentClient.desktop) return;
      try {
        const result = await agentClient.request<{ ports: string[] }>({ action: "list_arm_ports" });
        if (!disposed) setPorts(result.ports.filter(port => /^COM[1-9][0-9]*$/.test(port)));
      } catch { /* 保留选择；串口发现失败不代表设备已断开。 */ }
    };
    void refresh();
    const timer = setInterval(() => void refresh(), 10000);
    return () => { disposed = true; clearInterval(timer); };
  }, []);
  const selectedPort = value.startsWith("serial:") ? value.slice(7) : "";
  const options = selectedPort && !ports.includes(selectedPort) ? [selectedPort, ...ports] : ports;
  const entries = [{ value: "simulation", label: "仿真", icon: Box }, ...options.map(port => ({ value: `serial:${port}`, label: `真机 · ${port}`, icon: Cpu }))];
  const selected = entries.find(entry => entry.value === value) ?? entries[0];
  return <div ref={host} className="composer-target" onKeyDown={event => {
    if (event.key === "Escape") { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
    if (open && ["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault(); const buttons = [...(host.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? [])];
      const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
      buttons[(index + (event.key === "ArrowDown" ? 1 : buttons.length - 1)) % buttons.length]?.focus();
    }
  }}>
    <button ref={trigger} type="button" className="composer-target-trigger" aria-label={`执行目标：${selected.label}`} aria-haspopup="listbox" aria-controls={menuId} aria-expanded={open} disabled={disabled} onClick={() => setOpen(!open)}>
      <selected.icon size={14} /><span>{selected.label}</span><ChevronDown size={12} />
    </button>
    {open && !disabled && <div id={menuId} className="composer-target-menu" role="listbox" aria-label="机械臂执行目标">
      {entries.map(entry => <button key={entry.value} type="button" role="option" aria-selected={entry.value === value} onClick={() => { onChange(entry.value); setOpen(false); trigger.current?.focus(); }}>
        <entry.icon size={15} /><span>{entry.label}</span>{entry.value === value && <Check size={14} />}
      </button>)}
    </div>}
  </div>;
}

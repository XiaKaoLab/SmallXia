/** 功能：四分之一宽度的聊天侧栏，整合会话、技能和流式消息。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown, CircleAlert, History, MessageSquare, Plus, RefreshCw, Trash2, WandSparkles, X } from "lucide-react";
import { IconButton } from "../shared/IconButton";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";
import { useChat } from "./useChat";
import "./chat.css";

export function ChatSidebar() {
  const chat = useChat();
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [menu, setMenu] = useState<"sessions" | "skills" | null>(null);
  const [refreshError, setRefreshError] = useState("");
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!menu) return;
    const outside = (event: PointerEvent) => { if (!panel.current?.contains(event.target as Node)) setMenu(null); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setMenu(null); };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [menu]);
  const toggle = (name: "sessions" | "skills") => setMenu((value) => value === name ? null : name);
  const send = () => { const text = draft; setDraft(""); setMenu(null); void chat.send(text); };
  const notice = chat.error || refreshError;
  return <aside ref={panel} className="chat-sidebar" aria-label="小虾聊天侧栏">
    <header className="chat-header">
      <div className="chat-heading"><button className="heading-trigger" onClick={() => toggle("sessions")} disabled={chat.busy} aria-expanded={menu === "sessions"}>小虾<ChevronDown size={14} /></button><span className="model-label"><i className={chat.data.configured ? "connected" : ""} />{chat.data.model || "你的机械臂助手"}</span></div>
      <IconButton label="历史对话" onClick={() => toggle("sessions")} disabled={chat.busy}><History size={17} /></IconButton>
      <IconButton label="新建对话" disabled={chat.busy || chat.loading} onClick={() => { setMenu(null); navigate("/"); }}><Plus size={19} /></IconButton>
    </header>
    <AnimatePresence>
      {menu && <motion.section key={menu} className="chat-menu" aria-label={menu === "sessions" ? "会话列表" : "技能列表"} initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -3 }} transition={{ duration: 0.14 }}>
        <div className="menu-heading"><span>{menu === "sessions" ? "最近对话" : "为这轮对话选择技能"}</span><IconButton label="关闭列表" onClick={() => setMenu(null)}><X size={14} /></IconButton></div>
        <div className="menu-scroll">
          {menu === "sessions" ? chat.data.sessions.length ? chat.data.sessions.map((session) => <Link key={session.id} className={`menu-row ${session.id === chat.sessionId ? "selected" : ""}`} to={`/chat/${session.id}`} onClick={() => setMenu(null)}><MessageSquare size={14} /><span>{session.title}</span>{session.id === chat.sessionId && <Check size={14} />}</Link>) : <p className="menu-empty">第一段对话，从这里开始。</p>
            : chat.data.skills.length ? chat.data.skills.map((skill) => <button key={skill.name} className="menu-row skill-row" role="checkbox" aria-checked={chat.skills.includes(skill.name)} title={skill.description} onClick={() => chat.setSkills((values) => values.includes(skill.name) ? values.filter((value) => value !== skill.name) : [...values, skill.name])}><WandSparkles size={14} /><span><strong>{skill.name}</strong><small>{skill.description}</small></span>{chat.skills.includes(skill.name) && <Check size={14} />}</button>) : <p className="menu-empty">暂无可用技能</p>}
        </div>
        {menu === "sessions" && chat.sessionId && <button className="clear-conversation" disabled={chat.busy || chat.loading} onClick={() => { void chat.clear(); setMenu(null); }}><Trash2 size={14} />清空当前对话</button>}
      </motion.section>}
    </AnimatePresence>
    {chat.loading && <div className="chat-loading" role="status">正在加载对话…</div>}
    <MessageList messages={chat.messages} busy={chat.busy} />
    <footer className="chat-footer">
      {notice && <div className="chat-notice error" role="alert"><CircleAlert size={14} /><span>{notice}</span><IconButton label="重新连接" onClick={() => { setRefreshError(""); void chat.refresh().catch((failure: unknown) => setRefreshError(String(failure))); }}><RefreshCw size={14} /></IconButton></div>}
      {!chat.desktop ? <p className="chat-notice">请在桌面应用中连接助手。</p> : !chat.loading && !chat.error && !chat.data.configured ? <p className="chat-notice">配置模型和 API 密钥后，即可开始对话。</p> : null}
      {chat.skills.length > 0 && <div className="selected-skills">{chat.skills.map((skill) => <button key={skill} disabled={chat.busy} onClick={() => chat.setSkills((values) => values.filter((value) => value !== skill))}><WandSparkles size={11} />{skill}<X size={11} /></button>)}</div>}
      <Composer value={draft} onChange={setDraft} onSend={send} onStop={() => { void chat.stop(); }} busy={chat.busy} disabled={!chat.desktop || !chat.data.configured || chat.loading} skillCount={chat.skills.length} onSkills={() => toggle("skills")} />
      <p className="composer-caption">小虾的回答仅供参考，请核对重要信息。</p>
    </footer>
  </aside>;
}

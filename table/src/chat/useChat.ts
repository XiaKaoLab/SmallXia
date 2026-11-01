/** 功能：管理会话恢复、流式消息状态及停止生成。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { agentClient } from "./AgentClient";
import type { AgentEvent, Bootstrap, ChatMessage } from "./types";

const empty: Bootstrap = { sessions: [], skills: [], model: "", configured: false };

export function useChat() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(empty);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [bootLoading, setBootLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const loading = bootLoading || historyLoading;
  const [error, setError] = useState("");
  const active = useRef<{ id: string; cancelled: boolean; completed: boolean } | null>(null);

  const refresh = useCallback(async () => {
    if (!agentClient.desktop) return;
    const result = await agentClient.bootstrap();
    setData(result);
    setError("");
  }, []);

  useEffect(() => {
    let alive = true;
    if (!agentClient.desktop) return;
    setBootLoading(true);
    setError("");
    void agentClient.bootstrap().then((result) => {
      if (alive) setData(result);
    }).catch((failure: unknown) => { if (alive) setError(String(failure)); })
      .finally(() => { if (alive) setBootLoading(false); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    let alive = true;
    if (active.current) return;
    setMessages([]);
    setHistoryLoading(false);
    if (!sessionId || !agentClient.desktop) return;
    setHistoryLoading(true);
    setError("");
    void agentClient.request<{ messages: { role: "user" | "assistant"; content: string }[] }>({ action: "history", session_id: sessionId })
      .then((result) => {
        if (alive) setMessages(result.messages.map((message, index) => ({ ...message, id: `${sessionId}-${index}`, activities: [], status: "completed" })));
      }).catch((failure: unknown) => { if (alive) setError(String(failure)); })
      .finally(() => { if (alive) setHistoryLoading(false); });
    return () => { alive = false; };
  }, [sessionId]);

  useEffect(() => () => {
    const request = active.current;
    if (request) { request.cancelled = true; void agentClient.cancel(request.id).catch(() => undefined); }
  }, []);

  const send = useCallback(async (text: string) => {
    if (active.current || !text.trim() || !agentClient.desktop || !data.configured || loading) return;
    const request = { id: crypto.randomUUID(), cancelled: false, completed: false };
    active.current = request;
    setBusy(true);
    setError("");
    let id = sessionId;
    let completed = false;
    const assistantId = crypto.randomUUID();
    const update = (transform: (message: ChatMessage) => ChatMessage) => {
      setMessages((items) => items.map((message) => message.id === assistantId ? transform(message) : message));
    };
    try {
      if (!id) {
        id = (await agentClient.request<{ id: string }>({ action: "create" })).id;
        navigate(`/chat/${id}`, { replace: true });
      }
      if (request.cancelled) return;
      setMessages((items) => [...items,
        { id: crypto.randomUUID(), role: "user", content: text.trim(), activities: [], status: "completed" },
        { id: assistantId, role: "assistant", content: "", activities: [], status: "streaming" },
      ]);
      await agentClient.stream(request.id, id, text.trim(), skills, (event: AgentEvent) => {
        if (request.cancelled && event.type !== "completed") return;
        if (event.type === "delta") update((message) => ({ ...message, content: message.content + event.delta }));
        if (event.type === "skill_loaded") update((message) => ({ ...message, activities: [...message.activities, {
          id: `skill-${event.skill}`, name: event.skill, kind: "skill", status: "completed", output: "技能指令已加载",
        }] }));
        if (event.type === "tool_started") update((message) => ({ ...message, activities: [...message.activities, {
          id: event.call_id, name: event.name, kind: "tool", status: "running", output: "",
        }] }));
        if (event.type === "tool_delta") update((message) => ({ ...message, activities: message.activities.map((item) => item.id === event.call_id ? { ...item, output: item.output + event.delta } : item) }));
        if (event.type === "tool_completed") update((message) => ({ ...message, activities: message.activities.map((item) => item.id === event.call_id ? { ...item, output: event.output, status: event.failed ? "failed" : "completed" } : item) }));
        if (event.type === "completed") {
          request.cancelled = false;
          request.completed = true;
          completed = true;
          update((message) => ({ ...message, content: event.result.text, status: "completed", result: event.result }));
        }
      });
      if (!completed && !request.cancelled) throw new Error("回答在完成前结束，请重试");
    } catch (failure) {
      if (!request.cancelled && !completed) {
        setError(String(failure));
        update((message) => ({ ...message, status: "failed", activities: message.activities.map((item) => item.status === "running" ? { ...item, status: "failed" } : item) }));
      }
    } finally {
      if (request.cancelled) update((message) => ({ ...message, status: "cancelled", activities: message.activities.map((item) => item.status === "running" ? { ...item, status: "cancelled" } : item) }));
      active.current = null;
      setBusy(false);
      if (id) {
        if (completed) {
          await refresh().catch(() => undefined);
          if (!sessionId) navigate(`/chat/${id}`, { replace: true });
        } else {
          // 后端仅保存完整轮次；失败预览不混入下一次消息上下文。
          setData((value) => ({ ...value, sessions: value.sessions.some((session) => session.id === id) ? value.sessions : [{ id: id!, title: text.trim().slice(0, 48) }, ...value.sessions] }));
        }
      }
    }
  }, [data.configured, loading, navigate, refresh, sessionId, skills]);

  const stop = useCallback(async () => {
    const request = active.current;
    if (!request || request.completed) return;
    request.cancelled = true;
    try {
      await agentClient.cancel(request.id);
    } catch (failure) { request.cancelled = false; setError(`停止失败: ${String(failure)}`); }
  }, []);

  const clear = useCallback(async () => {
    if (busy || loading || !sessionId) return;
    try {
      await agentClient.request({ action: "clear", session_id: sessionId });
      setMessages([]);
      await refresh();
    } catch (failure) { setError(String(failure)); }
  }, [busy, loading, refresh, sessionId]);

  return { data, messages, skills, setSkills, busy, loading, error, sessionId, send, stop, clear, refresh, desktop: agentClient.desktop };
}

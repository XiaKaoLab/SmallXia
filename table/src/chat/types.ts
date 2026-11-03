/** 功能：定义与 Python Agent 一致的聊天和流式事件类型。
 * Created on 2026-11-01; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
export interface LLMResult { text: string; response_id: string; model: string; input_tokens: number | null; output_tokens: number | null }
export interface Skill { name: string; description: string }
export interface Session { id: string; title: string }
export interface Bootstrap { sessions: Session[]; skills: Skill[]; model: string; configured: boolean }
export interface Activity { id: string; name: string; kind: "skill" | "tool"; status: "running" | "completed" | "failed" | "cancelled"; output: string }
export type MessagePart = { type: "text"; id: string; text: string } | { type: "activity"; id: string };
export interface ChatMessage { id: string; role: "user" | "assistant"; content: string; activities: Activity[]; parts?: MessagePart[]; status?: "streaming" | "completed" | "failed" | "cancelled"; result?: LLMResult }
export type AgentEvent =
  | { type: "started"; session_id: string }
  | { type: "skill_loaded"; skill: string }
  | { type: "delta"; delta: string }
  | { type: "completed"; result: LLMResult }
  | { type: "error"; message: string }
  | { type: "tool_started"; call_id: string; name: string }
  | { type: "tool_delta"; call_id: string; delta: string }
  | { type: "tool_completed"; call_id: string; output: string; failed?: boolean };

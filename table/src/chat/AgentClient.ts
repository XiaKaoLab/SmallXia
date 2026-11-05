/** 功能：封装 Tauri Channel 与 Python Agent 的请求和取消操作。
 * Created on 2026-11-01; Updated on 2026-11-05
 * @author: https://github.com/Linmoqian
 */
import { Channel, invoke, isTauri } from "@tauri-apps/api/core";
import type { AgentEvent, Bootstrap } from "./types";
import { agentCursor } from "../interaction/AgentCursor";

export class AgentClient {
  readonly desktop = isTauri();

  private async dispatch<T extends { type: string }>(requestId: string, request: Record<string, unknown>, receive: (event: T) => void, terminal: (event: T) => boolean): Promise<void> {
    const channel = new Channel<T>();
    let finished = false;
    let finish!: () => void;
    const delivered = new Promise<void>((resolve) => { finish = resolve; });
    channel.onmessage = (event) => {
      receive(event);
      if (terminal(event)) { finished = true; finish(); }
    };
    let nativeError: unknown;
    try { await invoke("agent_request", { requestId, request, onEvent: channel }); }
    catch (error) { nativeError = error; }
    // IPC 命令结束与最后一个 Channel 回调分开到达时，等消息队列排空。
    if (!finished) {
      let timer: ReturnType<typeof setTimeout> | undefined;
      await Promise.race([delivered, new Promise<void>((resolve) => { timer = setTimeout(resolve, 2000); })]);
      clearTimeout(timer);
    }
    if (nativeError) throw nativeError;
    if (!finished) throw new Error("Agent 未发送完成事件");
  }

  async request<T>(request: Record<string, unknown>): Promise<T> {
    let value: T | undefined;
    let failure = "";
    try {
      await this.dispatch<{ type: "data"; data: T } | { type: "error"; message: string }>(crypto.randomUUID(), request, (event) => {
        if (event.type === "data") value = event.data;
        else failure = event.message;
      }, () => true);
    } catch (error) { throw new Error(failure || String(error)); }
    if (failure) throw new Error(failure);
    if (value === undefined) throw new Error("Agent 未返回结果");
    return value;
  }

  async hardwarePreview<T>(requestId:string,receive:(state:T)=>void):Promise<void>{
    await this.dispatch<{type:"hardware_preview";data:T}|{type:"error";message:string}|{type:"completed"}>(
      requestId,{action:"hardware_preview"},event=>{if(event.type==="hardware_preview")receive(event.data);},event=>event.type==="error"||event.type==="completed");
  }

  bootstrap(): Promise<Bootstrap> { return this.request({ action: "bootstrap" }); }

  async redTrackingPreview<T>(requestId:string,id:string,receive:(state:T)=>void):Promise<void>{
    let failure="";
    await this.dispatch<{type:"red_tracking";data:T}|{type:"error";message:string}|{type:"completed"}>(
      requestId,{action:"red_tracking_preview",id},event=>{
        if(event.type==="red_tracking")receive(event.data);
        if(event.type==="error")failure=event.message;
      },event=>event.type==="error"||event.type==="completed");
    if(failure)throw new Error(failure);
  }

  async calibrationPreview<T>(requestId: string, sessionId: string, receive: (frame: T) => void): Promise<void> {
    let failure = "";
    await this.dispatch<{ type: "calibration"; data: T } | { type: "completed" } | { type: "error"; message: string }>(
      requestId, { action: "camera_calibration_preview", session_id: sessionId }, event => {
        if (event.type === "calibration") receive(event.data);
        if (event.type === "error") failure = event.message;
      }, event => event.type === "completed" || event.type === "error");
    if (failure) throw new Error(failure);
  }

  async alignmentPreview<T>(requestId: string, sessionId: string, receive: (frame: T) => void): Promise<void> {
    let failure = "";
    await this.dispatch<{ type: "alignment"; data: T } | { type: "completed" } | { type: "error"; message: string }>(
      requestId, { action: "alignment_preview", session_id: sessionId }, event => {
        if (event.type === "alignment") receive(event.data);
        if (event.type === "error") failure = event.message;
      }, event => event.type === "completed" || event.type === "error");
    if (failure) throw new Error(failure);
  }

  async trainingPreview<T>(requestId: string, receive: (frame: T) => void): Promise<void> {
    let failure = "";
    await this.dispatch<{ type: "preview"; data: T } | { type: "completed" } | { type: "error"; message: string }>(
      requestId, { action: "reinforcement_preview" }, event => {
        if (event.type === "preview") receive(event.data);
        if (event.type === "error") failure = event.message;
      }, event => event.type === "completed" || event.type === "error");
    if (failure) throw new Error(failure);
  }

  async stream(requestId: string, sessionId: string, text: string, skills: string[], onEvent: (event: AgentEvent) => void): Promise<void> {
    let failure = "";
    let activeTool = "";
    try {
      await this.dispatch<AgentEvent>(requestId, { action: "run", session_id: sessionId, text, skill_names: skills }, (event) => {
        if (event.type === "error") failure = event.message;
        onEvent(event);
        if (event.type === "tool_started") {
          activeTool = event.call_id;
          agentCursor.toolStarted(event.call_id, event.name);
        } else if (event.type === "tool_completed") {
          agentCursor.finish(`tool:${event.call_id}`, event.failed);
          activeTool = "";
        }
      }, (event) => event.type === "completed" || event.type === "error");
    } catch (error) { throw new Error(failure || String(error)); }
    finally { if (activeTool) agentCursor.hide(`tool:${activeTool}`); }
    if (failure) throw new Error(failure);
  }

  cancel(requestId: string): Promise<void> { return invoke("agent_cancel", { requestId }); }
}

export const agentClient = new AgentClient();

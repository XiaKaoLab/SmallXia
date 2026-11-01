/** 功能：为开发控制台提供输入框填写和原生 WebView 截图接口。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import { blocksDebug, type BlocksDebugAPI } from "./BlocksDebug";
import { invoke, isTauri } from "@tauri-apps/api/core";

interface ScreenshotOptions { download?: boolean }
interface Screenshot { dataUrl: string; mimeType: "image/png"; width: number; height: number }
export interface WebViewDebugAPI {
  readonly blocks: BlocksDebugAPI;
  fillInput(selector: string, value: string): Promise<{ selector: string; length: number }>;
  screenshot(options?: ScreenshotOptions): Promise<Screenshot>;
}

declare global {
  interface Window { tableDebug?: WebViewDebugAPI }
}

const nextFrame = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

class WebViewDebug implements WebViewDebugAPI {
  readonly blocks = blocksDebug;
  private capturing = false;

  async fillInput(selector: string, value: string) {
    if (typeof selector !== "string" || typeof value !== "string") throw new Error("selector 和 value 必须为字符串");
    const matches = document.querySelectorAll(selector);
    if (matches.length !== 1) throw new Error(`选择器需要唯一匹配，当前匹配 ${matches.length} 个元素`);
    const element = matches[0];
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) {
      throw new Error("目标必须是 input 或 textarea");
    }
    if (element.disabled || element.readOnly || !element.getClientRects().length) {
      throw new Error("目标输入框不可编辑或不可见");
    }
    if (element instanceof HTMLInputElement && !["text", "search", "email", "url", "tel", "password", "number"].includes(element.type)) {
      throw new Error(`不支持填写 ${element.type} 类型输入框`);
    }
    if (element.maxLength >= 0 && value.length > element.maxLength) throw new Error("文本超过输入框长度限制");
    // 调用原生 setter 绕过 React 的实例 value tracker，再派发事件同步受控状态。
    const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    if (!setter) throw new Error("找不到输入框原生 setter");
    element.focus();
    setter.call(element, value);
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertReplacementText", data: value }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    await nextFrame();
    await nextFrame();
    if (!element.isConnected || element.value !== value) throw new Error("页面未保留填写值，请检查受控输入状态或输入类型");
    return { selector, length: value.length };
  }

  async screenshot(options: ScreenshotOptions = {}): Promise<Screenshot> {
    if (!isTauri()) throw new Error("原生截图需要 Tauri WebView，普通浏览器不支持");
    if (this.capturing) throw new Error("已有截图正在进行");
    this.capturing = true;
    try {
      await nextFrame();
      await nextFrame();
      const base64 = await invoke<string>("debug_webview_screenshot");
      const dataUrl = `data:image/png;base64,${base64}`;
      const image = new Image();
      image.src = dataUrl;
      await image.decode();
      if (options.download) {
        const anchor = document.createElement("a");
        anchor.href = dataUrl;
        anchor.download = `table-webview-${new Date().toISOString().replace(/[:.]/g, "-")}.png`;
        anchor.click();
      }
      return { dataUrl, mimeType: "image/png", width: image.naturalWidth, height: image.naturalHeight };
    } finally {
      this.capturing = false;
    }
  }
}

export function installWebViewDebug(): void {
  if (!import.meta.env.DEV) return;
  window.tableDebug = new WebViewDebug();
  if (import.meta.hot) import.meta.hot.dispose(() => { delete window.tableDebug; });
}

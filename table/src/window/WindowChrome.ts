/** 功能：封装 Tauri 窗口控制与最大化、焦点状态订阅。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";

export interface WindowState { maximized: boolean; focused: boolean }
export class WindowChrome {
  readonly available = isTauri();
  private readonly window = this.available ? getCurrentWindow() : undefined;
  minimize(): Promise<void> { return this.window?.minimize() ?? Promise.resolve(); }
  async toggleMaximize(): Promise<void> { await this.window?.toggleMaximize(); }
  close(): Promise<void> { return this.window?.close() ?? Promise.resolve(); }

  subscribe(receive: (state: WindowState) => void): () => void {
    const window = this.window;
    if (!window) return () => undefined;
    let disposed = false;
    let state: WindowState = { maximized: false, focused: true };
    const listeners: (() => void)[] = [];
    const publish = (update: Partial<WindowState>) => {
      state = { ...state, ...update };
      if (!disposed) receive(state);
    };
    const attach = async (pending: Promise<() => void>) => {
      try { const stop = await pending; if (disposed) stop(); else listeners.push(stop); }
      catch (error) { console.error("窗口状态订阅失败", error); }
    };
    void Promise.all([window.isMaximized(), window.isFocused()])
      .then(([maximized, focused]) => publish({ maximized, focused }))
      .catch(error => console.error("窗口状态读取失败", error));
    void attach(window.onResized(() => {
      void window.isMaximized().then(maximized => publish({ maximized }))
        .catch(error => console.error("窗口大小读取失败", error));
    }));
    void attach(window.onFocusChanged(event => publish({ focused: event.payload })));
    return () => { disposed = true; listeners.forEach(stop => stop()); };
  }
}

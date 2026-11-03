/** 功能：显示小虾台自定义标题栏、原生拖动区域与窗口控制按钮。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useState } from "react";
import { Minus, Square, Copy, X } from "lucide-react";
import { WindowChrome, type WindowState } from "./WindowChrome";
import "./titlebar.css";

export function Titlebar() {
  const [chrome] = useState(() => new WindowChrome());
  const [state, setState] = useState<WindowState>({ maximized: false, focused: true });
  const [error, setError] = useState("");
  useEffect(() => chrome.subscribe(setState), [chrome]);
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => setError(""), 3000);
    return () => clearTimeout(timer);
  }, [error]);
  async function control(action: () => Promise<void>) {
    try { await action(); setError(""); }
    catch (failure) { console.error("窗口控制失败", failure); setError("窗口操作失败"); }
  }
  return <header className="app-titlebar" data-focused={state.focused}>
    <div className="app-titlebar-drag" data-tauri-drag-region>
      <img className="app-titlebar-icon" src={`${import.meta.env.BASE_URL}branding/xiaoxia-app-icon-v1.png`} alt="" draggable={false} />
      <span className="app-titlebar-name">小虾台</span>
    </div>
    {error && <span className="app-titlebar-error" role="status">{error}</span>}
    <nav className="app-window-controls" aria-label="窗口控制">
      <button type="button" aria-label="最小化" title="最小化" disabled={!chrome.available} onClick={() => void control(() => chrome.minimize())}><Minus size={15} /></button>
      <button type="button" aria-label={state.maximized ? "还原窗口" : "最大化"} title={state.maximized ? "还原窗口" : "最大化"}
        disabled={!chrome.available} onClick={() => void control(() => chrome.toggleMaximize())}>{state.maximized ? <Copy size={13} /> : <Square size={13} />}</button>
      <button type="button" className="app-window-close" aria-label="关闭窗口" title="关闭窗口" disabled={!chrome.available} onClick={() => void control(() => chrome.close())}><X size={17} /></button>
    </nav>
  </header>;
}

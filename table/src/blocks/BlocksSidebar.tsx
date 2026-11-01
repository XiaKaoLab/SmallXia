/** 功能：左侧 Blockly 单积木工作区及 Python 代码预览与导出。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState } from "react";
import * as Blockly from "blockly/core";
import * as Zh from "blockly/msg/zh-hans";
import { pythonGenerator } from "blockly/python";
import { BLOCK_TYPE, JOINTS, parseModelLimits, registerPositionBlock } from "./positionBlock";
import "./blocks.css";

export function BlocksSidebar() {
  const host = useRef<HTMLDivElement>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!host.current) return;
    const element = host.current;
    const abort = new AbortController();
    let workspace: Blockly.WorkspaceSvg | undefined;
    let observer: ResizeObserver | undefined;
    async function initialize() {
      try {
        const response = await fetch(`${import.meta.env.BASE_URL}robots/so101/so101_new_calib.urdf`, { signal: abort.signal });
        if (!response.ok) throw new Error("机械臂限位加载失败");
        const limits = parseModelLimits(await response.text());
        if (abort.signal.aborted) return;
        Blockly.setLocale(Zh);
        registerPositionBlock(limits);
        workspace = Blockly.inject(element, {
          media: `${import.meta.env.BASE_URL}blockly-media/`,
          renderer: "zelos", sounds: false, trashcan: false,
          scrollbars: true, move: { scrollbars: true, drag: true, wheel: true },
          zoom: { controls: false, wheel: false, startScale: 0.9 },
          grid: { spacing: 20, length: 1, colour: "#d4dedb", snap: false },
        });
        const block = workspace.newBlock(BLOCK_TYPE);
        block.initSvg();
        block.render();
        block.moveBy(16, 24);
        const update = () => {
          if (!workspace) return;
          try { setCode(pythonGenerator.workspaceToCode(workspace)); setError(""); setNotice(""); }
          catch (failure) { setCode(""); setError(String(failure)); }
        };
        let edited = false;
        workspace.addChangeListener((event) => {
          if (event.type === Blockly.Events.BLOCK_CHANGE) edited = true;
          update();
        });
        update();
        observer = new ResizeObserver(() => { if (workspace) Blockly.svgResize(workspace); });
        observer.observe(element);
        // API 可用时以当前显示目标初始化；不可用时保留模型范围内的零位。
        try {
          const stateResponse = await fetch("http://127.0.0.1:8766/api/v1/robots/table/state", {
            signal: AbortSignal.any([abort.signal, AbortSignal.timeout(1000)]),
          });
          if (!stateResponse.ok) return;
          const state = await stateResponse.json();
          if (abort.signal.aborted || state.unit !== "rad" || state.physical !== false) return;
          const positions = state.joint_positions;
          if (!positions || JOINTS.some(([name]) => !Number.isFinite(positions[name]) || positions[name] < limits[name].lower || positions[name] > limits[name].upper)) return;
          // 用户开始编辑后不覆盖字段。
          if (edited) return;
          for (const [name] of JOINTS) block.setFieldValue(String(positions[name]), name);
          workspace.clearUndo();
          update();
        } catch { /* 模型服务不在线时仍可编辑和导出。 */ }
      } catch (failure) {
        if (!abort.signal.aborted) setError(String(failure));
      }
    }
    void initialize();
    return () => { abort.abort(); observer?.disconnect(); workspace?.dispose(); };
  }, []);

  async function copy() {
    try { await navigator.clipboard.writeText(code); setNotice("已复制 Python"); }
    catch { setNotice("复制失败，可下载 Python 文件"); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([code], { type: "text/x-python;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url; link.download = "set_arm_position.py"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <aside className="blocks-sidebar" aria-label="机械臂积木编程">
    <header className="blocks-heading"><h2>积木编程</h2><span>Python</span></header>
    <p className="blocks-description">设置六轴角度，生成模型控制代码。</p>
    <div ref={host} className="blocks-workspace" aria-label="设置机械臂位置积木" />
    <section className="blocks-code" aria-label="生成的 Python 代码">
      <div className="blocks-code-toolbar"><span>Python 代码</span><div>
        <button type="button" disabled={!code} onClick={() => void copy()}>复制</button>
        <button type="button" disabled={!code} onClick={download}>下载 .py</button>
      </div></div>
      <pre tabIndex={0}><code>{code || "正在加载积木…"}</code></pre>
    </section>
    <p className="blocks-status" role="status">{error || notice || "通过本机 API 控制显示模型"}</p>
  </aside>;
}

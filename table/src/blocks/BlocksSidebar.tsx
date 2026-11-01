/** 功能：左侧 Blockly 单积木工作区与 Python 后台运行。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState } from "react";
import { blocksDebug } from "../debug/BlocksDebug";
import { Play } from "lucide-react";
import { agentClient } from "../chat/AgentClient";
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
  const [running, setRunning] = useState(false);
  const runLock = useRef(false);

  useEffect(() => {
    if (!host.current) return;
    const element = host.current;
    const abort = new AbortController();
    let workspace: Blockly.WorkspaceSvg | undefined;
    let observer: ResizeObserver | undefined;
    let detachDebug: (() => void) | undefined;
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
        if (import.meta.env.DEV) detachDebug = blocksDebug.attach(workspace, limits, () => { edited = true; update(); });
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
          if (edited || workspace.getBlockById(block.id) !== block) return;
          for (const [name] of JOINTS) block.setFieldValue(String(positions[name]), name);
          workspace.clearUndo();
          update();
        } catch { /* 模型服务不在线时仍可编辑和导出。 */ }
      } catch (failure) {
        if (!abort.signal.aborted) setError(String(failure));
      }
    }
    void initialize();
    return () => { abort.abort(); detachDebug?.(); observer?.disconnect(); workspace?.dispose(); };
  }, []);

  async function run() {
    if (!code || runLock.current) return;
    if (!agentClient.desktop) { setError("运行 Python 需要打开 Tauri 桌面窗口"); return; }
    runLock.current = true;
    setRunning(true);
    setError("");
    setNotice("正在运行 Python…");
    try {
      const result = await agentClient.request<{ output: string; exit_code: number }>({ action: "run_program", source: code });
      setNotice(result.output.trim() ? `已运行：${result.output.trim()}` : "Python 运行完成");
    } catch (failure) {
      setError(String(failure));
      setNotice("");
    } finally {
      runLock.current = false;
      setRunning(false);
    }
  }

  return <aside className="blocks-sidebar" aria-label="机械臂积木编程">
    <header className="blocks-heading"><h2>积木编程</h2><div className="blocks-heading-actions"><span>Python</span>
      <button type="button" className="blocks-run" onClick={() => void run()} disabled={!code || running}
        aria-label={running ? "正在运行 Python" : "运行 Python"} aria-busy={running} title="运行 Python">
        <Play size={15} fill="currentColor" /><span>{running ? "运行中" : "运行"}</span>
      </button>
    </div></header>
    <p className="blocks-description">设置六轴角度，点击运行更新模型。</p>
    <div ref={host} className="blocks-workspace" aria-label="设置机械臂位置积木" />
    <p className="blocks-status" role="status">{error || notice || "通过本机 API 控制显示模型"}</p>
  </aside>;
}

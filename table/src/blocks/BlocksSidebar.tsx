/** 功能：左侧 Blockly 单积木工作区与 Python 后台运行。
 * Created on 2026-11-01; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState } from "react";
import { jointPreview } from "../JointPreview";
import { LiveJointRunner } from "./LiveJointRunner";
import { blocksDebug } from "../debug/BlocksDebug";
import { CAMERA_BLOCK_TYPE, registerCameraBlock } from "./cameraBlock";
import { Camera, Play } from "lucide-react";
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
  const liveRef = useRef<LiveJointRunner | null>(null);
  const workspaceRef = useRef<Blockly.WorkspaceSvg | null>(null);
  const [cameraAdded, setCameraAdded] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!host.current) return;
    const element = host.current;
    const abort = new AbortController();
    let workspace: Blockly.WorkspaceSvg | undefined;
    let observer: ResizeObserver | undefined;
    const onLimit = (event: Event) => { setNotice(`已限制：${(event as CustomEvent<string>).detail}`); };
    window.addEventListener("table:pose-limit", onLimit);
    const onConfirmed = (event: Event) => {
      const block = workspace?.getBlocksByType(BLOCK_TYPE, false)[0];
      if (!block) return;
      const positions = (event as CustomEvent<Record<string, number>>).detail;
      for (const [name] of JOINTS) block.setFieldValue(String(positions[name]), name);
    };
    window.addEventListener("table:joint-confirmed", onConfirmed);
    const live = new LiveJointRunner((message) => { if (!abort.signal.aborted) setNotice(message); });
    liveRef.current = live;
    let detachDebug: (() => void) | undefined;
    async function initialize() {
      try {
        const response = await fetch(`${import.meta.env.BASE_URL}robots/so101/so101_new_calib.urdf`, { signal: abort.signal });
        if (!response.ok) throw new Error("机械臂限位加载失败");
        const limits = parseModelLimits(await response.text());
        if (abort.signal.aborted) return;
        Blockly.setLocale(Object.fromEntries(Object.entries(Zh).filter((entry): entry is [string, string] => typeof entry[1] === "string")));
        registerPositionBlock(limits, (block) => {
          const source = pythonGenerator.forBlock[BLOCK_TYPE](block, pythonGenerator);
          if (typeof source === "string") live.schedule(source);
        });
        registerCameraBlock();
        workspace = Blockly.inject(element, {
          media: `${import.meta.env.BASE_URL}blockly-media/`,
          maxInstances: { [BLOCK_TYPE]: 1, [CAMERA_BLOCK_TYPE]: 1 },
          renderer: "zelos", sounds: false, trashcan: false,
          scrollbars: true, move: { scrollbars: true, drag: true, wheel: true },
          zoom: { controls: false, wheel: false, startScale: 0.9 },
          grid: { spacing: 20, length: 1, colour: "#d4dedb", snap: false },
        });
        workspaceRef.current = workspace;
        setReady(true);
        const block = workspace.newBlock(BLOCK_TYPE);
        block.initSvg();
        block.render();
        block.moveBy(16, 24);
        const update = () => {
          if (!workspace) return;
          setCameraAdded(workspace.getBlocksByType(CAMERA_BLOCK_TYPE, false).length > 0);
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
    return () => { abort.abort(); window.removeEventListener("table:pose-limit", onLimit); window.removeEventListener("table:joint-confirmed", onConfirmed); live.dispose(); liveRef.current = null; workspaceRef.current = null; detachDebug?.(); observer?.disconnect(); workspace?.dispose(); };
  }, []);

  function addCamera() {
    const workspace = workspaceRef.current;
    if (!workspace || workspace.getBlocksByType(CAMERA_BLOCK_TYPE, false).length) return;
    const block = workspace.newBlock(CAMERA_BLOCK_TYPE);
    block.initSvg(); block.render(); block.moveBy(16, 340);
    workspace.centerOnBlock(block.id);
    setCameraAdded(true);
    setCode(pythonGenerator.workspaceToCode(workspace));
  }

  async function run() {
    if (!code || runLock.current) return;
    if (!agentClient.desktop) { setError("运行 Python 需要打开 Tauri 桌面窗口"); return; }
    runLock.current = true;
    const revision = jointPreview.revision;
    setRunning(true);
    setError("");
    setNotice("正在运行 Python…");
    try {
      await liveRef.current?.pause();
      const result = await agentClient.request<{ output: string; exit_code: number }>({ action: "run_program", source: code });
      for (const line of result.output.trim().split("\n")) {
        try {
          const receipt = JSON.parse(line);
          if (receipt.limited && receipt.applied_joint_positions) jointPreview.confirm(receipt.applied_joint_positions, revision);
        } catch { /* 相机积木等非 JSON 文本不属于关节回执。 */ }
      }
      setNotice(result.output.trim() ? `已运行：${result.output.trim()}` : "Python 运行完成");
    } catch (failure) {
      setError(String(failure));
      setNotice("");
    } finally {
      liveRef.current?.resume();
      runLock.current = false;
      setRunning(false);
    }
  }

  return <aside className="blocks-sidebar" aria-label="机械臂积木编程">
    <header className="blocks-heading"><h2>积木编程</h2><div className="blocks-heading-actions">
      <button type="button" className="blocks-add-camera" onClick={addCamera} disabled={!ready || cameraAdded || running} aria-label="添加虚拟相机积木" title="添加虚拟相机积木"><Camera size={15} /><span>相机</span></button>
      <button type="button" className="blocks-run" onClick={() => void run()} disabled={!code || running}
        aria-label={running ? "正在运行 Python" : "运行 Python"} aria-busy={running} title="运行 Python">
        <Play size={15} fill="currentColor" /><span>{running ? "运行中" : "运行"}</span>
      </button>
    </div></header>
    <div ref={host} className="blocks-workspace" aria-label="设置机械臂位置积木" />
    <p className="blocks-status" role="status">{error || notice || "通过本机 API 控制显示模型"}</p>
  </aside>;
}

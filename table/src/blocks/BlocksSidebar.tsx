/** 功能：左侧分类 Blockly 工作区与 Python 后台运行。
 * Created on 2026-11-01; Updated on 2026-11-04
 * @author: https://github.com/Linmoqian
 */
import { registerCoordinateBlock } from "./coordinateBlock";
import { QiLingBlocks, qiLingCatalog } from "./QiLingBlocks";
import { UiMessage } from "../shared/UiMessage";
import { useEffect, useRef, useState } from "react";
import { jointPreview } from "../JointPreview";
import { LiveJointRunner } from "./LiveJointRunner";
import { blocksDebug } from "../debug/BlocksDebug";
import { registerCameraCalibrationBlock } from "./cameraCalibrationBlock";
import { registerArmMappingBlock } from "./armMappingBlock";
import { registerCalibrationBlock } from "./calibrationBlock";
import { registerCameraBlock } from "./cameraBlock";
import { cameraCatalog } from "./CameraCatalog";
import { onnxModelCatalog } from "./OnnxModelCatalog";
import { armTargetCatalog } from "./ArmTargetCatalog";
import { registerFrameBlocks } from "./frameBlocks";
import { BlocksToolbox, BLOCK_LIMITS } from "./BlocksToolbox";
import { BlocksControlBridge } from "./BlocksControlBridge";
import { DataBlocks } from "./dataBlocks";
import { PolicyBlocks } from "./policyBlocks";
import { WorkflowBlocks } from "./WorkflowBlocks";
import { workflowCatalog } from "./WorkflowCatalog";
import { ProgramClient, type ProgramReceipt } from "./ProgramClient";
import { HardwareBlocks } from "./HardwareBlocks";
import { WorkflowTemplate } from "./WorkflowTemplate";
import { WorkspaceStore } from "./WorkspaceStore";
import { ProgramLibrary } from "./ProgramLibrary";
import "blockly/blocks";
import { Play, Square } from "lucide-react";
import { agentClient } from "../chat/AgentClient";
import * as Blockly from "blockly/core";
import * as Zh from "blockly/msg/zh-hans";
import { pythonGenerator } from "blockly/python";
import { BLOCK_TYPE, JOINTS, parseModelLimits, registerPositionBlock } from "./positionBlock";
import "./blocks.css";

export function BlocksSidebar() {
  const host = useRef<HTMLDivElement>(null);
  const qiling = useRef(new QiLingBlocks());
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [running, setRunning] = useState(false);
  const [ready, setReady] = useState(false);
  const runLock = useRef(false);
  const programRef = useRef<ProgramClient | null>(null);
  const liveRef = useRef<LiveJointRunner | null>(null);
  const workspaceRef = useRef<Blockly.WorkspaceSvg | null>(null);
  const runRef = useRef<() => Promise<unknown>>(async () => undefined);
  runRef.current = () => run(true);

  useEffect(() => {
    if (!host.current) return;
    const element = host.current;
    const abort = new AbortController();
    let workspace: Blockly.WorkspaceSvg | undefined;
    let observer: ResizeObserver | undefined;
    const onLimit = () => { setNotice("已到运动边界"); };
    window.addEventListener("table:pose-limit", onLimit);
    const onConfirmed = (event: Event) => {
      if (workspace?.getBlocksByType(BLOCK_TYPE, false).length !== 1) return;
      const block = workspace?.getBlocksByType(BLOCK_TYPE, false)[0];
      if (!block || block.getFieldValue("TARGET") !== "simulation") return;
      const positions = (event as CustomEvent<Record<string, number>>).detail;
      for (const [name] of JOINTS) block.setFieldValue(String(positions[name]), name);
    };
    window.addEventListener("table:joint-confirmed", onConfirmed);
    const live = new LiveJointRunner((message) => { if (!abort.signal.aborted) setNotice(message); });
    liveRef.current = live;
    let detachDebug: (() => void) | undefined;
    let detachCameras: (() => void) | undefined;
    let detachQiLing: (() => void) | undefined;
    let detachModels: (() => void) | undefined;
    let detachWorkflow: (() => void) | undefined;
    let detachArmTargets: (() => void) | undefined;
    let controlBridge: BlocksControlBridge | undefined;
    async function initialize() {
      try {
        const response = await fetch(`${import.meta.env.BASE_URL}robots/so100/so100_mid_calib.urdf`, { signal: abort.signal });
        if (!response.ok) throw new Error("机械臂限位加载失败");
        const limits = parseModelLimits(await response.text());
        if (abort.signal.aborted) return;
        Blockly.setLocale(Object.fromEntries(Object.entries(Zh).filter((entry): entry is [string, string] => typeof entry[1] === "string")));
        registerPositionBlock(limits, (block) => {
          const source = pythonGenerator.forBlock[BLOCK_TYPE](block, pythonGenerator);
          if (typeof source === "string") live.schedule(source);
        });
        registerCameraBlock();
        registerCalibrationBlock();
        registerArmMappingBlock();
        registerCoordinateBlock();
        registerCameraCalibrationBlock();
        registerFrameBlocks();
        new PolicyBlocks().register();
        qiling.current.register();
        new DataBlocks().register();
        new WorkflowBlocks().register();
        new HardwareBlocks().register();
        pythonGenerator.addReservedWords("CameraFrameClient,virtual_frame,real_frame,_block_wait,_ball_job,_onnx_job");
        workspace = Blockly.inject(element, {
          media: `${import.meta.env.BASE_URL}blockly-media/`,
          maxInstances: BLOCK_LIMITS,
          maxBlocks: 100, toolbox: new BlocksToolbox().definition(),
          renderer: "zelos", sounds: false, trashcan: false,
          scrollbars: true, move: { scrollbars: true, drag: true, wheel: true },
          zoom: { controls: false, wheel: false, startScale: 0.9 },
          grid: { spacing: 20, length: 1, colour: "#d4dedb", snap: false },
        });
        workspaceRef.current = workspace;
        detachCameras = cameraCatalog.attach(workspace);
        detachArmTargets = armTargetCatalog.attach(workspace);
        detachModels = onnxModelCatalog.attach(workspace);
        detachQiLing = qiLingCatalog.attach(workspace);
        detachWorkflow = workflowCatalog.attach(workspace);
        new WorkflowTemplate().attach(workspace);
        workspace.registerButtonCallback("CREATE_VARIABLE", () => {
          if (workspace) Blockly.Variables.createVariableButtonHandler(workspace);
        });
        const storage = new WorkspaceStore();
        const restored = storage.restore(workspace);
        const block = restored ? undefined : workspace.newBlock(BLOCK_TYPE);
        if (block) { block.initSvg(); block.render(); block.moveBy(16, 24); }
        const update = () => {
          if (!workspace) return;
          try { setCode(pythonGenerator.workspaceToCode(workspace)); setError(""); setNotice(""); }
          catch (failure) { setCode(""); setError(UiMessage.error(failure)); }
        };
        let edited = false;
        workspace.addChangeListener((event) => {
          if (event.type === Blockly.Events.BLOCK_CHANGE) edited = true;
          update();
          if (!event.isUiEvent && workspace) storage.save(workspace);
        });
        update();
        detachDebug = blocksDebug.attach(workspace, limits, () => { edited = true; update(); });
        setReady(true);
        controlBridge = new BlocksControlBridge(() => runRef.current(), () => runLock.current);
        void controlBridge.start();
        const program = new ProgramClient(setNotice, receiveReceipt);
        void program.recover().then(async job => {
          if (abort.signal.aborted || !job || runLock.current) { program.dispose(); return; }
          runLock.current = true; setRunning(true); programRef.current = program;
          await live.pause();
          try { await program.observe(job); }
          catch (failure) { if (!abort.signal.aborted) setError(UiMessage.error(failure)); }
          finally {
            program.dispose();
            if (programRef.current === program) {
              programRef.current = null; runLock.current = false;
              if (!abort.signal.aborted) { live.resume(); setRunning(false); }
            }
          }
        }).catch(() => program.dispose());
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
          if (!block || edited || workspace.getBlockById(block.id) !== block) return;
          for (const [name] of JOINTS) block.setFieldValue(String(positions[name]), name);
          workspace.clearUndo();
          update();
        } catch { /* 模型服务不在线时仍可编辑和导出。 */ }
      } catch (failure) {
        if (!abort.signal.aborted) setError(UiMessage.error(failure));
      }
    }
    void initialize();
    return () => { abort.abort(); programRef.current?.dispose(); qiling.current.finish(); programRef.current = null; window.removeEventListener("table:pose-limit", onLimit); window.removeEventListener("table:joint-confirmed", onConfirmed); live.dispose(); liveRef.current = null; workspaceRef.current = null; controlBridge?.stop(); detachDebug?.(); detachCameras?.(); detachArmTargets?.(); detachModels?.(); detachQiLing?.(); detachWorkflow?.(); observer?.disconnect(); workspace?.dispose(); };
  }, []);

  function receiveReceipt(receipt: ProgramReceipt) {
    if (receipt.qiling) qiling.current.receive(workspaceRef.current ?? undefined, receipt.qiling);
    if (receipt.ball_training && ["ball_pickup", "ball_onnx_rollout"].includes(receipt.ball_training.kind)) window.dispatchEvent(new CustomEvent("table:ball-training-started", { detail: receipt.ball_training }));
    if (receipt.camera_calibration?.id) window.dispatchEvent(new CustomEvent("table:camera-calibration-start", { detail: receipt.camera_calibration }));
    if(receipt.coordinate_calibration)window.dispatchEvent(new CustomEvent("table:coordinate-calibration",{detail:receipt.coordinate_calibration}));
    if (receipt.display_alignment?.id) window.dispatchEvent(new CustomEvent("table:alignment-start", { detail: receipt.display_alignment }));
    if (receipt.limited && receipt.applied_joint_positions) jointPreview.confirm(receipt.applied_joint_positions, jointPreview.revision);
  }

  async function run(strict = false) {
    if (runLock.current) { if (strict) throw new Error("已有程序运行中"); return; }
    const source = workspaceRef.current ? pythonGenerator.workspaceToCode(workspaceRef.current) : code;
    if (!source.trim()) { if (strict) throw new Error("工作区为空"); return; }
    if (!agentClient.desktop) { setError("请在桌面应用中运行"); if (strict) throw new Error("需要 Tauri 窗口"); return; }
    runLock.current = true;
    setRunning(true);
    setError("");
    setNotice("运行中…");
    try {
      await liveRef.current?.pause();
      const program = new ProgramClient(setNotice, receiveReceipt);
      programRef.current = program;
      let job;
      try { job = await program.start(source); }
      catch (failure) { program.dispose(); programRef.current = null; throw failure; }
      // 调试接口立即获得可查询任务回执；UI 继续等待真实完成。
      const completion = program.observe(job).catch(failure => { setError(UiMessage.error(failure)); setNotice(""); })
        .finally(() => { qiling.current.finish(); program.dispose(); programRef.current = null; liveRef.current?.resume(); runLock.current = false; setRunning(false); void workflowCatalog.refresh(); });
      void completion;
      return { program: job };
    } catch (failure) {
      setError(UiMessage.error(failure));
      setNotice("");
      if (strict) throw failure;
    } finally {
      if (!programRef.current) { liveRef.current?.resume(); runLock.current = false; setRunning(false); }
    }
  }

  return <aside className="blocks-sidebar" aria-label="机械臂积木编程">
    <header className="blocks-heading"><h2>积木编程</h2><div className="blocks-heading-actions">
      <ProgramLibrary disabled={!ready || running} snapshot={() => blocksDebug.exportWorkspace()}
        open={async snapshot => {
          if (runLock.current) throw new Error("请先停止当前程序");
          await liveRef.current?.pause();
          try {
            blocksDebug.importWorkspace(snapshot);
            if (workspaceRef.current) new WorkspaceStore().save(workspaceRef.current);
          } finally { liveRef.current?.resume(); }
        }}
        notice={message => { setError(""); setNotice(message); }} error={failure => { setNotice(""); setError(UiMessage.error(failure)); }} />
      <button type="button" className="blocks-run" onClick={() => void run()} disabled={!code || running}
        aria-label={running ? "运行中" : "运行"} aria-busy={running} title="运行">
        <Play size={15} fill="currentColor" /><span>{running ? "运行中" : "运行"}</span>
      </button>
      {running && <button type="button" className="blocks-run blocks-stop" onClick={() => void programRef.current?.stop().catch(failure => setError(UiMessage.error(failure)))} aria-label="停止程序"><Square size={14} fill="currentColor" /><span>停止</span></button>}
    </div></header>
    <div ref={host} className="blocks-workspace" aria-label="器灵、机械臂、相机、逻辑、变量、策略和数据积木工作区" />
    {(error || notice) && <p className="blocks-status" role="status">{error || notice}</p>}
  </aside>;
}

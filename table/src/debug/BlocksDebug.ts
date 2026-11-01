/** 功能：为开发接口管理分类积木、字段和保留连接/变量的工作区快照。
 * Created on 2026-11-01; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { CAMERA_BLOCK_TYPE } from "../blocks/cameraBlock";
import { BLOCK_TYPE, JOINTS, type Limits } from "../blocks/positionBlock";
import { cameraCatalog } from "../blocks/CameraCatalog";
import { FRAME_CAPTURE, FRAME_VARIABLE } from "../blocks/frameBlocks";
import { BlocksToolbox, BLOCK_LIMITS, TOOLBOX_TYPES } from "../blocks/BlocksToolbox";
import { POLICY_RL_BALL } from "../blocks/policyBlocks";
import { ONNX_EXPORT, ONNX_RUN, ONNX_TYPES } from "../blocks/OnnxPolicyBlocks";
import { armTargetCatalog } from "../blocks/ArmTargetCatalog";

export interface BlockSnapshot { id: string; type: string; fields: Record<string, number | string>; x: number; y: number }
export interface BlocksSnapshot { version: 2; state: Record<string, unknown> }

class WorkspaceManager {
  constructor(private readonly workspace: Blockly.WorkspaceSvg,
    private readonly limits: Limits, private readonly changed: () => void) {}

  visualTarget(id?: string, field?: string): { x: number; y: number } | undefined {
    const block = id ? this.workspace.getBlockById(id) : null;
    const element = (field ? block?.getField(field)?.getSvgRoot() : null) ?? block?.getSvgRoot();
    const bounds = this.workspace.getParentSvg().getBoundingClientRect();
    const rect = element?.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return undefined;
    return {
      x: Math.max(bounds.left + 12, Math.min(bounds.right - 20, rect ? rect.left + Math.min(rect.width / 2, 70) : bounds.left + bounds.width / 2)),
      y: Math.max(bounds.top + 12, Math.min(bounds.bottom - 30, rect ? rect.top + Math.min(rect.height / 2, 24) : bounds.top + 60)),
    };
  }

  private known(type: string): void {
    if (!TOOLBOX_TYPES.includes(type)) throw new Error(`未知积木类型：${type}`);
  }
  private get(id: string): Blockly.BlockSvg {
    const block = this.workspace.getBlockById(id);
    if (!block) throw new Error(`找不到积木：${id}`);
    this.known(block.type); return block;
  }
  private position(x: number, y: number): void {
    if (![x, y].every(v => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 100000)) throw new Error("积木坐标必须是 ±100000 内的有限数值");
  }
  private fields(block: Blockly.Block): Record<string, string | number> {
    return Object.fromEntries(block.inputList.flatMap(input => input.fieldRow.filter(field => !!field.name)
      .map(field => [field.name!, field.getValue() as string | number])));
  }
  private apply(block: Blockly.Block, fields: Record<string, string | number>): void {
    if (!fields || typeof fields !== "object" || Array.isArray(fields)) throw new Error("fields 必须为字段对象");
    for (const [name, value] of Object.entries(fields)) {
      const field = block.getField(name);
      if (!field || !["string", "number"].includes(typeof value) || (typeof value === "number" && !Number.isFinite(value))) throw new Error(`无效字段：${name}`);
      if (block.type === BLOCK_TYPE && name !== "TARGET") {
        const limit = this.limits[name];
        if (!limit || typeof value !== "number" || value < limit.lower || value > limit.upper) throw new Error(`关节字段越界：${name}`);
      }
      const old = field.getValue();
      field.setValue(value);
      if (String(field.getValue()) !== String(value)) { field.setValue(old); throw new Error(`字段 ${name} 未接受该值`); }
    }
  }
  types() {
    const labels: Record<string, string> = { [BLOCK_TYPE]: "设置机械臂位置", [CAMERA_BLOCK_TYPE]: "装配相机",
      [FRAME_CAPTURE]: "获取画面", [FRAME_VARIABLE]: "画面变量", [POLICY_RL_BALL]: "强化学习 · 拿取小球",
      [ONNX_EXPORT]: "导出抓球模型 ONNX", [ONNX_RUN]: "ONNX 推理 · 拿取小球" };
    return TOOLBOX_TYPES.map(type => ({ type, label: labels[type] || type, maxInstances: BLOCK_LIMITS[type] ?? 100,
      fields: type === BLOCK_TYPE ? [{ name: "TARGET", label: "机械臂", options: armTargetCatalog.options().map(([, id]) => id) },
        ...JOINTS.map(([name, label]) => ({ name, label, unit: "rad", ...this.limits[name] }))]
        : type === POLICY_RL_BALL ? [{ name: "NUM_ENVS", label: "同时训练数量", lower: 1, upper: 16 },
          { name: "ROUNDS", label: "每环境训练轮数", lower: 1, upper: 10000 }, { name: "DEVICE", label: "设备", options: ["cpu", "cuda"] }]
        : ONNX_TYPES.includes(type) ? [{ name: "MODEL_ID", label: "模型任务 ID 或 latest" },
          ...(type === ONNX_RUN ? [{ name: "ROUNDS", label: "推理回合数", lower: 1, upper: 1000 }] : [])]
        : [FRAME_CAPTURE, FRAME_VARIABLE].includes(type) ? [{ name: "SOURCE", label: "来源", options: cameraCatalog.options().map(([, id]) => id) }] : [] }));
  }
  list(): BlockSnapshot[] {
    return this.workspace.getAllBlocks(false).map(block => {
      const p = block.getRelativeToSurfaceXY();
      return { id: block.id, type: block.type, fields: this.fields(block), x: p.x, y: p.y };
    });
  }
  create(fields: Record<string, number | string> = {}, x = 16, y = 24, type = BLOCK_TYPE): BlockSnapshot {
    this.known(type); this.position(x, y);
    if (this.workspace.getAllBlocks(false).length >= 100 || this.workspace.getBlocksByType(type, false).length >= (BLOCK_LIMITS[type] ?? 100)) throw new Error("积木数量已达上限");
    const block = this.workspace.newBlock(type);
    try { this.apply(block, fields); block.initSvg(); block.render(); block.moveBy(x, y); }
    catch (error) { block.dispose(false); throw error; }
    this.changed(); return this.list().find(item => item.id === block.id)!;
  }
  setFields(id: string, fields: Record<string, number | string>): BlockSnapshot {
    const block = this.get(id); const backup = this.fields(block);
    Blockly.Events.setGroup(true);
    try { this.apply(block, fields); }
    catch (error) { this.apply(block, backup); throw error; }
    finally { Blockly.Events.setGroup(false); }
    this.changed(); return this.list().find(item => item.id === id)!;
  }
  move(id: string, x: number, y: number): BlockSnapshot {
    this.position(x, y); const block = this.get(id); const p = block.getRelativeToSurfaceXY();
    block.moveBy(x - p.x, y - p.y); this.changed(); return this.list().find(item => item.id === id)!;
  }
  connect(parentId: string, childId: string, inputName = ""): BlockSnapshot[] {
    const parent = this.get(parentId), child = this.get(childId);
    if (parent === child) throw new Error("不能连接积木自身");
    const target = inputName ? parent.getInput(inputName)?.connection : parent.nextConnection;
    if (!target) throw new Error("父积木没有该连接口");
    const source = target.type === Blockly.ConnectionType.INPUT_VALUE ? child.outputConnection : child.previousConnection;
    if (!source) throw new Error("子积木类型与连接口不匹配");
    target.connect(source); this.changed(); return this.list();
  }
  remove(id: string): void { this.get(id).dispose(false); this.changed(); }
  clear(): void { this.workspace.clear(); this.changed(); }
  python(): string { return pythonGenerator.workspaceToCode(this.workspace); }
  exportWorkspace(): BlocksSnapshot { return { version: 2, state: Blockly.serialization.workspaces.save(this.workspace) }; }

  importWorkspace(value: unknown): BlocksSnapshot {
    if (JSON.stringify(value).length > 1000000) throw new Error("工作区快照超过大小限制");
    const snapshot = typeof value === "string" ? JSON.parse(value) : value;
    if (!snapshot || ![1, 2].includes(snapshot.version)) throw new Error("工作区快照需要 version=1 或 2");
    let native: Record<string, unknown>;
    if (snapshot.version === 1) {
      if (!Array.isArray(snapshot.blocks)) throw new Error("旧版快照缺少 blocks");
      native = { blocks: { languageVersion: 0, blocks: snapshot.blocks.map((item: BlockSnapshot) => {
        this.known(item.type); this.position(item.x, item.y);
        return { type: item.type, id: item.id, x: item.x, y: item.y, fields: item.type === CAMERA_BLOCK_TYPE ? {} : item.fields };
      }) } };
    } else native = snapshot.state;
    if (!native || typeof native !== "object" || Array.isArray(native)) throw new Error("工作区状态无效");
    // 先在无界面的工作区还原并验证；非法输入不会清空当前积木。
    const trial = new Blockly.Workspace();
    let validated: Record<string, unknown>;
    try {
      Blockly.serialization.workspaces.load(native, trial);
      const blocks = trial.getAllBlocks(false);
      if (blocks.length > 100) throw new Error("最多允许 100 个积木");
      for (const block of blocks) {
        this.known(block.type);
        const point = block.getRelativeToSurfaceXY(); this.position(point.x, point.y);
        if (blocks.filter(other => other.type === block.type).length > (BLOCK_LIMITS[block.type] ?? 100)) throw new Error("同类积木数量超出上限");
        if (block.type === BLOCK_TYPE) this.apply(block, this.fields(block));
      }
      validated = Blockly.serialization.workspaces.save(trial);
    } finally { trial.dispose(); }
    const backup = Blockly.serialization.workspaces.save(this.workspace);
    try { Blockly.serialization.workspaces.load(validated, this.workspace); }
    catch (error) { Blockly.serialization.workspaces.load(backup, this.workspace); throw error; }
    this.changed(); return this.exportWorkspace();
  }
}

export class BlocksDebugAPI {
  private manager: WorkspaceManager | undefined;
  attach(workspace: Blockly.WorkspaceSvg, limits: Limits, changed: () => void): () => void {
    const manager = new WorkspaceManager(workspace, limits, changed); this.manager = manager;
    return () => { if (this.manager === manager) this.manager = undefined; };
  }
  ready(): boolean { return !!this.manager; }
  visualTarget(id?: string, field?: string): { x: number; y: number } | undefined {
    return this.manager?.visualTarget(id, field);
  }
  private active(): WorkspaceManager {
    if (!this.manager) throw new Error("Blockly 工作区尚未就绪或已卸载"); return this.manager;
  }
  types() { return this.active().types(); }
  catalog() { return { toolbox: new BlocksToolbox().definition(), types: this.active().types() }; }
  list() { return this.active().list(); }
  create(fields: Record<string, number | string> = {}, x = 16, y = 24, type = BLOCK_TYPE) { return this.active().create(fields, x, y, type); }
  createCamera(fields: Record<string, number | string> = {}, x = 16, y = 340) { return this.active().create(fields, x, y, CAMERA_BLOCK_TYPE); }
  setFields(id: string, fields: Record<string, number | string>) { return this.active().setFields(id, fields); }
  move(id: string, x: number, y: number) { return this.active().move(id, x, y); }
  connect(parentId: string, childId: string, inputName = "") { return this.active().connect(parentId, childId, inputName); }
  remove(id: string) { this.active().remove(id); }
  clear() { this.active().clear(); }
  python() { return this.active().python(); }
  exportWorkspace() { return this.active().exportWorkspace(); }
  importWorkspace(snapshot: unknown) { return this.active().importWorkspace(snapshot); }
}
export const blocksDebug = new BlocksDebugAPI();

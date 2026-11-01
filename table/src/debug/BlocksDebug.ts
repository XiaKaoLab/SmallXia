/** 功能：为 WebView 开发接口管理当前 Blockly 工作区和六轴位置积木。
 * Created on 2026-11-01; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { FRAME_CAPTURE, FRAME_VARIABLE } from "../blocks/frameBlocks";
import { CAMERA_BLOCK_TYPE } from "../blocks/cameraBlock";
import { BLOCK_TYPE, JOINTS, type Limits } from "../blocks/positionBlock";

export interface BlockSnapshot {
  id: string;
  type: string;
  fields: Record<string, number | string>;
  x: number;
  y: number;
}
export interface BlocksSnapshot { version: 1; blocks: BlockSnapshot[] }

class WorkspaceManager {
  constructor(private readonly workspace: Blockly.WorkspaceSvg,
    private readonly limits: Limits, private readonly changed: () => void) {}

  private get(id: string): Blockly.BlockSvg {
    const block = this.workspace.getBlockById(id);
    if (!block || ![BLOCK_TYPE, CAMERA_BLOCK_TYPE, FRAME_CAPTURE, FRAME_VARIABLE].includes(block.type)) throw new Error(`找不到位置积木：${id}`);
    return block;
  }

  private specs(type: string): Record<string, { label: string; lower?: number; upper?: number; options?: string[]; unit?: string }> {
    if (type === BLOCK_TYPE) return Object.fromEntries(JOINTS.map(([name, label]) => [name, { label, unit: "rad", ...this.limits[name] }]));
    if (type === CAMERA_BLOCK_TYPE) return {};
    if ([FRAME_CAPTURE, FRAME_VARIABLE].includes(type)) return { SOURCE: { label: "来源", options: ["virtual", "real"] } };
    throw new Error(`未知积木类型：${type}`);
  }

  private validateFields(fields: Record<string, number | string>, type: string): void {
    if (!fields || typeof fields !== "object" || Array.isArray(fields)) throw new Error("fields 必须为字段对象");
    const specs = this.specs(type);
    for (const [name, value] of Object.entries(fields)) {
      const spec = Object.prototype.hasOwnProperty.call(specs, name) ? specs[name] : undefined;
      if (!spec || (spec.options ? typeof value !== "string" || !spec.options.includes(value)
        : typeof value !== "number" || !Number.isFinite(value) || value < spec.lower! || value > spec.upper!)) {
        throw new Error(`字段 ${name} 未知或超出允许范围`);
      }
    }
  }

  private validatePosition(x: number, y: number): void {
    if (![x, y].every((value) => typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= 100000)) {
      throw new Error("积木坐标必须是 ±100000 内的有限数值");
    }
  }

  types() {
    return [BLOCK_TYPE, CAMERA_BLOCK_TYPE, FRAME_CAPTURE, FRAME_VARIABLE].map((type) => ({ type,
      label: ({ [BLOCK_TYPE]: "设置机械臂位置", [CAMERA_BLOCK_TYPE]: "装配相机", [FRAME_CAPTURE]: "获取画面", [FRAME_VARIABLE]: "画面变量" })[type], maxInstances: [FRAME_CAPTURE, FRAME_VARIABLE].includes(type) ? 2 : 1,
      fields: Object.entries(this.specs(type)).map(([name, spec]) => ({ name, ...spec })) }));
  }

  list(): BlockSnapshot[] {
    return this.workspace.getAllBlocks(false).map((block) => {
      const position = block.getRelativeToSurfaceXY();
      return { id: block.id, type: block.type, x: position.x, y: position.y,
        fields: Object.fromEntries(Object.entries(this.specs(block.type)).map(([name, spec]) =>
          [name, spec.options ? String(block.getFieldValue(name)) : Number(block.getFieldValue(name))])) };
    });
  }

  create(fields: Record<string, number | string> = {}, x = 16, y = 24, type = BLOCK_TYPE): BlockSnapshot {
    this.validateFields(fields, type);
    this.validatePosition(x, y);
    if (this.workspace.getBlocksByType(type, false).length >= ([FRAME_CAPTURE, FRAME_VARIABLE].includes(type) ? 2 : 1)) throw new Error("此类积木已达到数量限制，请先删除已有同类积木");
    const block = this.workspace.newBlock(type);
    for (const [name, value] of Object.entries(fields)) block.setFieldValue(String(value), name);
    block.initSvg(); block.render(); block.moveBy(x, y);
    this.changed();
    return this.list().find((item) => item.id === block.id)!;
  }

  setFields(id: string, fields: Record<string, number | string>): BlockSnapshot {
    const block = this.get(id);
    this.validateFields(fields, block.type);
    Blockly.Events.setGroup(true);
    try { for (const [name, value] of Object.entries(fields)) block.setFieldValue(String(value), name); }
    finally { Blockly.Events.setGroup(false); }
    this.changed();
    return this.list().find((item) => item.id === id)!;
  }

  move(id: string, x: number, y: number): BlockSnapshot {
    this.validatePosition(x, y);
    const block = this.get(id);
    const current = block.getRelativeToSurfaceXY();
    block.moveBy(x - current.x, y - current.y);
    this.changed();
    return this.list().find((item) => item.id === id)!;
  }

  remove(id: string): void { this.get(id).dispose(false); this.changed(); }
  clear(): void { this.workspace.clear(); this.changed(); }
  python(): string { return pythonGenerator.workspaceToCode(this.workspace); }
  exportWorkspace(): BlocksSnapshot { return { version: 1, blocks: this.list() }; }

  importWorkspace(value: unknown): BlocksSnapshot {
    const state = typeof value === "string" ? JSON.parse(value) : value;
    if (!state || state.version !== 1 || !Array.isArray(state.blocks) || state.blocks.length > 6) {
      throw new Error("工作区快照需要 version=1 和最多六个积木");
    }
    // 全部检查通过后才替换工作区，非法导入不删除现有积木。
    for (const block of state.blocks) {
      if (!block || ![BLOCK_TYPE, CAMERA_BLOCK_TYPE, FRAME_CAPTURE, FRAME_VARIABLE].includes(block.type) || typeof block.id !== "string" || !block.id || block.id.length > 128) {
        throw new Error("快照包含未知积木类型或无效 ID");
      }
      if (block.type === CAMERA_BLOCK_TYPE) block.fields = {}; // 旧快照迁移为固定安装，不再提供可编辑参数。
      this.validateFields(block.fields, block.type);
      if (Object.keys(block.fields).length !== Object.keys(this.specs(block.type)).length) throw new Error("快照必须包含完整字段");
      this.validatePosition(block.x, block.y);
    }
    if (state.blocks.some((item: BlockSnapshot) => state.blocks.filter((other: BlockSnapshot) => other.type === item.type).length > ([FRAME_CAPTURE, FRAME_VARIABLE].includes(item.type) ? 2 : 1))
      || new Set(state.blocks.map((block: BlockSnapshot) => block.id)).size !== state.blocks.length) throw new Error("快照包含重复类型或 ID");
    Blockly.Events.setGroup(true);
    try {
      this.workspace.clear();
      for (const item of state.blocks) {
        const block = this.workspace.newBlock(item.type, item.id);
        for (const [name, value] of Object.entries(item.fields)) block.setFieldValue(String(value), name);
        block.initSvg(); block.render(); block.moveBy(item.x, item.y);
      }
    } finally { Blockly.Events.setGroup(false); }
    this.changed();
    return this.exportWorkspace();
  }
}

export class BlocksDebugAPI {
  private manager: WorkspaceManager | undefined;

  attach(workspace: Blockly.WorkspaceSvg, limits: Limits, changed: () => void): () => void {
    const manager = new WorkspaceManager(workspace, limits, changed);
    this.manager = manager;
    return () => { if (this.manager === manager) this.manager = undefined; };
  }

  ready(): boolean { return !!this.manager; }
  private active(): WorkspaceManager {
    if (!this.manager) throw new Error("Blockly 工作区尚未就绪或已卸载");
    return this.manager;
  }
  types() { return this.active().types(); }
  list() { return this.active().list(); }
  create(fields: Record<string, number | string> = {}, x = 16, y = 24, type = BLOCK_TYPE) { return this.active().create(fields, x, y, type); }
  createCamera(fields: Record<string, number | string> = {}, x = 16, y = 340) { return this.active().create(fields, x, y, CAMERA_BLOCK_TYPE); }
  setFields(id: string, fields: Record<string, number | string>) { return this.active().setFields(id, fields); }
  move(id: string, x: number, y: number) { return this.active().move(id, x, y); }
  remove(id: string) { this.active().remove(id); }
  clear() { this.active().clear(); }
  python() { return this.active().python(); }
  exportWorkspace() { return this.active().exportWorkspace(); }
  importWorkspace(snapshot: unknown) { return this.active().importWorkspace(snapshot); }
}

export const blocksDebug = new BlocksDebugAPI();

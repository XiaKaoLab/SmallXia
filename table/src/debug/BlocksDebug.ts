/** 功能：为 WebView 开发接口管理当前 Blockly 工作区和六轴位置积木。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { BLOCK_TYPE, JOINTS, type Limits } from "../blocks/positionBlock";

export interface BlockSnapshot {
  id: string;
  type: string;
  fields: Record<string, number>;
  x: number;
  y: number;
}
export interface BlocksSnapshot { version: 1; blocks: BlockSnapshot[] }

class WorkspaceManager {
  constructor(private readonly workspace: Blockly.WorkspaceSvg,
    private readonly limits: Limits, private readonly changed: () => void) {}

  private get(id: string): Blockly.BlockSvg {
    const block = this.workspace.getBlockById(id);
    if (!block || block.type !== BLOCK_TYPE) throw new Error(`找不到位置积木：${id}`);
    return block;
  }

  private validateFields(fields: Record<string, number>): void {
    if (!fields || typeof fields !== "object" || Array.isArray(fields)) throw new Error("fields 必须为字段对象");
    for (const [name, value] of Object.entries(fields)) {
      const limit = Object.prototype.hasOwnProperty.call(this.limits, name) ? this.limits[name] : undefined;
      if (!limit || typeof value !== "number" || !Number.isFinite(value) || value < limit.lower || value > limit.upper) {
        throw new Error(`字段 ${name} 未知、不是有限数值或超出模型限位`);
      }
    }
  }

  private validatePosition(x: number, y: number): void {
    if (![x, y].every((value) => typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= 100000)) {
      throw new Error("积木坐标必须是 ±100000 内的有限数值");
    }
  }

  types() {
    return [{ type: BLOCK_TYPE, label: "设置机械臂位置", maxInstances: 1,
      fields: JOINTS.map(([name, label]) => ({ name, label, unit: "rad", ...this.limits[name] })) }];
  }

  list(): BlockSnapshot[] {
    return this.workspace.getAllBlocks(false).map((block) => {
      const position = block.getRelativeToSurfaceXY();
      return { id: block.id, type: block.type, x: position.x, y: position.y,
        fields: Object.fromEntries(JOINTS.map(([name]) => [name, Number(block.getFieldValue(name))])) };
    });
  }

  create(fields: Record<string, number> = {}, x = 16, y = 24): BlockSnapshot {
    this.validateFields(fields);
    this.validatePosition(x, y);
    if (this.workspace.getAllBlocks(false).length) throw new Error("当前仅支持一个位置积木，请先删除或清空");
    const block = this.workspace.newBlock(BLOCK_TYPE);
    for (const [name, value] of Object.entries(fields)) block.setFieldValue(String(value), name);
    block.initSvg(); block.render(); block.moveBy(x, y);
    this.changed();
    return this.list()[0];
  }

  setFields(id: string, fields: Record<string, number>): BlockSnapshot {
    this.validateFields(fields);
    const block = this.get(id);
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
    if (!state || state.version !== 1 || !Array.isArray(state.blocks) || state.blocks.length > 1) {
      throw new Error("工作区快照需要 version=1 和最多一个积木");
    }
    // 全部检查通过后才替换工作区，非法导入不删除现有积木。
    for (const block of state.blocks) {
      if (!block || block.type !== BLOCK_TYPE || typeof block.id !== "string" || !block.id || block.id.length > 128) {
        throw new Error("快照包含未知积木类型或无效 ID");
      }
      this.validateFields(block.fields);
      if (Object.keys(block.fields).length !== JOINTS.length) throw new Error("快照必须包含完整六轴字段");
      this.validatePosition(block.x, block.y);
    }
    Blockly.Events.setGroup(true);
    try {
      this.workspace.clear();
      for (const item of state.blocks) {
        const block = this.workspace.newBlock(BLOCK_TYPE, item.id);
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
  create(fields: Record<string, number> = {}, x = 16, y = 24) { return this.active().create(fields, x, y); }
  setFields(id: string, fields: Record<string, number>) { return this.active().setFields(id, fields); }
  move(id: string, x: number, y: number) { return this.active().move(id, x, y); }
  remove(id: string) { this.active().remove(id); }
  clear() { this.active().clear(); }
  python() { return this.active().python(); }
  exportWorkspace() { return this.active().exportWorkspace(); }
  importWorkspace(snapshot: unknown) { return this.active().importWorkspace(snapshot); }
}

export const blocksDebug = new BlocksDebugAPI();

/** 功能：按名称持久保存积木程序的完整快照，与自动恢复草稿分开存储。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import type { BlocksSnapshot } from "../debug/BlocksDebug";

export interface SavedProgram { id: string; name: string; updatedAt: number; snapshot: BlocksSnapshot }

export class ProgramStore {
  constructor(private readonly key = "xiaoxia.blocks.programs.v1") {}

  list(): SavedProgram[] {
    const raw = localStorage.getItem(this.key);
    if (!raw) return [];
    const data = JSON.parse(raw);
    if (data.version !== 1 || !Array.isArray(data.programs) || data.programs.some((item: SavedProgram) =>
      !item || typeof item.id !== "string" || typeof item.name !== "string" || !Number.isFinite(item.updatedAt)
      || item.snapshot?.version !== 2 || !item.snapshot.state)) throw new Error("保存的程序列表无法读取");
    return data.programs.sort((a: SavedProgram, b: SavedProgram) => b.updatedAt - a.updatedAt);
  }

  private write(programs: SavedProgram[]): void {
    try { localStorage.setItem(this.key, JSON.stringify({ version: 1, programs })); }
    catch { throw new Error("本地保存失败，请检查存储空间"); }
  }

  save(name: string, snapshot: BlocksSnapshot): SavedProgram {
    const title = name.trim();
    if (!title || title.length > 60) throw new Error("请输入 1–60 字的程序名称");
    if (snapshot.version !== 2 || !snapshot.state || JSON.stringify(snapshot).length > 1000000) throw new Error("程序内容无效或过大");
    const programs = this.list();
    const previous = programs.find(program => program.name === title);
    const saved = { id: previous?.id ?? crypto.randomUUID(), name: title, updatedAt: Date.now(), snapshot };
    this.write([saved, ...programs.filter(program => program.id !== saved.id)]);
    return saved;
  }

  remove(id: string): void { this.write(this.list().filter(program => program.id !== id)); }
}

/** 功能：积木侧栏的命名保存与打开入口，沿用现有轻量弹层。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Plus, Save, Trash2, X } from "lucide-react";
import { IconButton } from "../shared/IconButton";
import type { BlocksSnapshot } from "../debug/BlocksDebug";
import { ProgramStore, type SavedProgram } from "./ProgramStore";

interface Props {
  disabled: boolean;
  snapshot: () => BlocksSnapshot;
  open: (snapshot: BlocksSnapshot) => Promise<void>;
  notice: (message: string) => void;
  error: (failure: unknown) => void;
}

export function ProgramLibrary({ disabled, snapshot, open, notice, error }: Props) {
  const [store] = useState(() => new ProgramStore());
  const [mode, setMode] = useState<"save" | "open" | null>(null);
  const [programs, setPrograms] = useState<SavedProgram[]>([]);
  const [name, setName] = useState("");
  const [currentId, setCurrentId] = useState("");
  const [opening, setOpening] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const unavailable = disabled || opening;
  const current = programs.find(program => program.id === currentId);
  useEffect(() => {
    try {
      const saved = store.list();
      const activeId = store.activeId();
      setPrograms(saved); setCurrentId(activeId);
      setName(saved.find(program => program.id === activeId)?.name ?? "");
    } catch { /* 打开菜单时显示读取错误，避免阻断工作区。 */ }
  }, [store]);
  useEffect(() => {
    if (!mode) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setMode(null); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setMode(null); };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [mode]);

  function show(next: "save" | "open") {
    try { setPrograms(store.list()); setMode(mode === next ? null : next); }
    catch (failure) { error(failure); }
  }

  async function switchProgram(program: SavedProgram) {
    if (unavailable) return;
    if (program.id === currentId) { setMode(null); return; }
    setOpening(true);
    try {
      const previous = snapshot();
      const entries = store.list();
      const source = entries.find(entry => entry.id === currentId)
        ?? entries.find(entry => JSON.stringify(entry.snapshot) === JSON.stringify(previous));
      if (source) store.save(source.name, previous);
      else {
        const names = new Set(entries.map(entry => entry.name));
        const automaticName = ["程序一", "程序二", "程序三"].find(title => !names.has(title)) ?? "未命名程序";
        // 先保存未命名草稿；已满时阻止切换，避免覆盖未保存内容。
        store.save(automaticName, previous);
      }
      await open(program.snapshot);
      store.select(program.id);
      setCurrentId(program.id); setName(program.name); setPrograms(store.list()); setMode(null); notice("已切换");
    } catch (failure) { error(failure); }
    finally { setOpening(false); }
  }

  return <div className="program-library" ref={root}>
    <button type="button" className="program-button program-selector" disabled={unavailable} onClick={() => show("open")} aria-label="选择程序" aria-expanded={mode === "open"} aria-haspopup="dialog"><span>{current?.name ?? "选择程序"}</span><ChevronDown size={14} /></button>
    <button type="button" className="program-button" disabled={unavailable} onClick={() => { setName(current?.name ?? ""); show("save"); }} aria-expanded={mode === "save"} aria-haspopup="dialog"><Save size={15} />保存</button>
    {mode && <section className="program-library-panel" role="dialog" aria-label={mode === "save" ? "保存积木程序" : "打开积木程序"}>
      <div className="program-library-heading"><span>{mode === "save" ? "保存程序" : `选择程序 · ${programs.length}/3`}</span><IconButton label="关闭程序列表" onClick={() => setMode(null)}><X size={14} /></IconButton></div>
      {mode === "save" ? <form onSubmit={event => {
        event.preventDefault();
        if (unavailable) return;
        try { const saved = store.save(name, snapshot()); setName(saved.name); setCurrentId(saved.id); setPrograms(store.list()); setMode(null); notice("已保存"); }
        catch (failure) { error(failure); }
      }}>
        <input aria-label="程序名称" placeholder="程序名称" value={name} maxLength={60} autoFocus onChange={event => setName(event.target.value)} />
        <button type="submit" className="program-save" disabled={unavailable || !name.trim()}>保存</button>
      </form> : <div className="program-library-list">
        {!programs.length && <p>暂无保存的程序</p>}
        {programs.map(program => <div className="program-library-row" key={program.id}>
          <button type="button" disabled={unavailable} title={program.name} aria-pressed={program.id === currentId} onClick={() => void switchProgram(program)}><span>{program.name}</span>{program.id === currentId && <Check size={14} />}</button>
          <IconButton label={`删除程序 ${program.name}`} disabled={unavailable} onClick={() => {
            try { store.remove(program.id); setPrograms(store.list()); if (program.id === currentId) { setCurrentId(""); setName(""); } notice("已删除"); }
            catch (failure) { error(failure); }
          }}><Trash2 size={13} /></IconButton>
        </div>)}
        {programs.length < ProgramStore.limit && <button type="button" className="program-button program-copy" disabled={unavailable} onClick={() => { setName(""); setMode("save"); }}><Plus size={14} />另存一份</button>}
      </div>}
    </section>}
  </div>;
}

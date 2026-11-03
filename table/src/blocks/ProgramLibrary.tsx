/** 功能：积木侧栏的命名保存与打开入口，沿用现有轻量弹层。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState } from "react";
import { FolderOpen, Save, Trash2, X } from "lucide-react";
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
  const [opening, setOpening] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const unavailable = disabled || opening;
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

  return <div className="program-library" ref={root}>
    <button type="button" className="program-button" disabled={unavailable} onClick={() => show("save")} aria-expanded={mode === "save"} aria-haspopup="dialog"><Save size={15} />保存</button>
    <button type="button" className="program-button" disabled={unavailable} onClick={() => show("open")} aria-expanded={mode === "open"} aria-haspopup="dialog"><FolderOpen size={15} />打开</button>
    {mode && <section className="program-library-panel" role="dialog" aria-label={mode === "save" ? "保存积木程序" : "打开积木程序"}>
      <div className="program-library-heading"><span>{mode === "save" ? "保存程序" : "已保存的程序"}</span><IconButton label="关闭程序列表" onClick={() => setMode(null)}><X size={14} /></IconButton></div>
      {mode === "save" ? <form onSubmit={event => {
        event.preventDefault();
        if (unavailable) return;
        try { const saved = store.save(name, snapshot()); setName(saved.name); setMode(null); notice("已保存"); }
        catch (failure) { error(failure); }
      }}>
        <input aria-label="程序名称" placeholder="程序名称" value={name} maxLength={60} autoFocus onChange={event => setName(event.target.value)} />
        <button type="submit" className="program-save" disabled={unavailable || !name.trim()}>保存</button>
      </form> : <div className="program-library-list">
        {!programs.length && <p>暂无保存的程序</p>}
        {programs.map(program => <div className="program-library-row" key={program.id}>
          <button type="button" disabled={unavailable} title={program.name} onClick={() => {
            setOpening(true);
            void open(program.snapshot).then(() => { setName(program.name); setMode(null); notice("已打开"); })
              .catch(error).finally(() => setOpening(false));
          }}>{program.name}</button>
          <IconButton label={`删除程序 ${program.name}`} disabled={unavailable} onClick={() => {
            try { store.remove(program.id); setPrograms(store.list()); notice("已删除"); }
            catch (failure) { error(failure); }
          }}><Trash2 size={13} /></IconButton>
        </div>)}
      </div>}
    </section>}
  </div>;
}

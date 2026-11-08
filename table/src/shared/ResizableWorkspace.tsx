/** 功能：使用 Motion 实时调整左右侧栏宽度，保留中间视图并支持键盘及触摸操作。
 * Created on 2026-11-08; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { motion, useMotionTemplate, useMotionValue, useMotionValueEvent, type MotionValue } from "motion/react";
import { SidebarWidths, type SidebarSide, type SidebarSizes } from "./SidebarWidths";
import "./resizable-workspace.css";

interface Props { left: ReactNode; center: ReactNode; right: ReactNode }
interface HandleProps {
  side: SidebarSide; width: MotionValue<number>; otherWidth: MotionValue<number>; maximum: () => number;
  begin: () => void; resize: (delta: number) => void; finish: () => void;
  keyboard: (key: string, shift: boolean) => void; reset: () => void;
}
function ResizeHandle({ side, width, otherWidth, maximum, begin, resize, finish, keyboard, reset }: HandleProps) {
  const [value, setValue] = useState(Math.round(width.get()));
  const [, refresh] = useState(0);
  useMotionValueEvent(width, "change", next => setValue(Math.round(next)));
  useMotionValueEvent(otherWidth, "change", () => refresh(next => next + 1));
  return <motion.div className={`sidebar-resizer sidebar-resizer-${side}`} role="separator" tabIndex={0}
    aria-label={side === "left" ? "调整积木区宽度" : "调整对话区宽度"} aria-orientation="vertical"
    aria-valuemin={SidebarWidths.min[side]} aria-valuemax={Math.round(maximum())} aria-valuenow={value}
    aria-valuetext={`${value} 像素`} title="拖动调整宽度，双击恢复默认"
    onPointerDown={event => { if (event.button !== 0) return; event.preventDefault(); event.stopPropagation(); event.currentTarget.focus(); event.currentTarget.setPointerCapture(event.pointerId); }}
    onFocus={() => refresh(next => next + 1)}
    onPanStart={begin} onPan={(_, info) => resize(info.offset.x)} onPanEnd={finish}
    onPointerCancel={finish} onLostPointerCapture={finish} onDoubleClick={reset}
    onKeyDown={event => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) { event.preventDefault(); keyboard(event.key, event.shiftKey); } }}
    whileHover="active" whileFocus="active" initial="idle">
    <motion.span className="sidebar-resizer-grip" variants={{ idle: { opacity: .25, scaleY: 1 }, active: { opacity: 1, scaleY: 1.35 } }} transition={{ duration: .14 }} />
  </motion.div>;
}

export function ResizableWorkspace({ left, center, right }: Props) {
  const host = useRef<HTMLElement>(null);
  const [model] = useState(() => new SidebarWidths());
  const [initial] = useState(() => model.load(window.innerWidth));
  const leftWidth = useMotionValue(initial.left), rightWidth = useMotionValue(initial.right);
  const columns = useMotionTemplate`${leftWidth}px minmax(0, 1fr) ${rightWidth}px`;
  const start = useRef<SidebarSizes>(initial);
  const preferred = useRef<SidebarSizes>(initial);
  const dragging = useRef<SidebarSide | null>(null);
  const sizes = (): SidebarSizes => ({ left: leftWidth.get(), right: rightWidth.get() });
  const total = () => host.current?.clientWidth || window.innerWidth;
  const apply = (value: SidebarSizes) => { leftWidth.set(value.left); rightWidth.set(value.right); };
  const save = () => { preferred.current = sizes(); model.save(preferred.current); };
  const finish = () => { if (!dragging.current) return; dragging.current = null; host.current?.removeAttribute("data-resizing"); save(); };
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      const next = model.fit(preferred.current, element.clientWidth);
      leftWidth.set(next.left); rightWidth.set(next.right);
    });
    observer.observe(element);
    return () => { observer.disconnect(); };
  }, [model, leftWidth, rightWidth]);
  const handle = (side: SidebarSide) => <ResizeHandle side={side} width={side === "left" ? leftWidth : rightWidth} otherWidth={side === "left" ? rightWidth : leftWidth}
    maximum={() => model.max(side, sizes(), total())}
    begin={() => { start.current = sizes(); dragging.current = side; host.current?.setAttribute("data-resizing", side); }}
    resize={delta => { if (dragging.current !== side) return; apply(model.resize(side, start.current[side] + (side === "left" ? delta : -delta), sizes(), total())); }}
    finish={finish} reset={() => { apply(model.resize(side, model.defaults(total())[side], sizes(), total())); save(); }}
    keyboard={(key, shift) => {
      const width = sizes()[side], step = shift ? 40 : 10;
      const next = key === "Home" ? SidebarWidths.min[side] : key === "End" ? model.max(side, sizes(), total())
        : width + (key === "ArrowRight" ? step : -step) * (side === "left" ? 1 : -1);
      apply(model.resize(side, next, sizes(), total())); save();
    }} />;
  return <motion.main ref={host} className="workspace workspace-resizable" style={{ gridTemplateColumns: columns }}>
    <div className="resizable-sidebar resizable-sidebar-left">{left}{handle("left")}</div>
    {center}
    <div className="resizable-sidebar resizable-sidebar-right">{handle("right")}{right}</div>
  </motion.main>;
}

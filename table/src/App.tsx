/** 功能：挂载并释放唯一的机械臂模型视图。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef } from "react";
import { RobotViewer } from "./RobotViewer";
import "./App.css";
export default function App() {
  const host = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!host.current) return;
    const viewer = new RobotViewer(host.current);
    return () => viewer.dispose();
  }, []);
  return <main ref={host} className="robot-viewer" aria-label="机械臂三维视图" />;
}

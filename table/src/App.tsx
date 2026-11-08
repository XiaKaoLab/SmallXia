/** 功能：组合机械臂工作区、路由与聊天侧栏。
 * Created on 2026-11-01; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
import { useEffect, useRef } from "react";
import { ResizableWorkspace } from "./shared/ResizableWorkspace";
import { RobotViewer } from "./RobotViewer";
import { HashRouter, Route, Routes } from "react-router";
import { MotionConfig } from "motion/react";
import { BlocksSidebar } from "./blocks/BlocksSidebar";
import { ChatSidebar } from "./chat/ChatSidebar";
import { BallTrainingProgress } from "./blocks/BallTrainingProgress";
import { Titlebar } from "./window/Titlebar";
import "./App.css";
export default function App() {
  const host = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!host.current) return;
    const viewer = new RobotViewer(host.current);
    return () => viewer.dispose();
  }, []);
  return <MotionConfig reducedMotion="user"><HashRouter><div className="app-shell"><Titlebar /><ResizableWorkspace left={<BlocksSidebar />}
    center={<section ref={host} className="robot-viewer" aria-label="机械臂三维视图"><BallTrainingProgress /></section>}
    right={<Routes><Route path="/" element={<ChatSidebar />} /><Route path="/chat/:sessionId" element={<ChatSidebar />} /><Route path="*" element={<ChatSidebar />} /></Routes>}
  /></div></HashRouter></MotionConfig>;
}

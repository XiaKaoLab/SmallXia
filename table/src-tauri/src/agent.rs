// 功能：通过隐藏的 Python 子进程和 Tauri Channel 桥接 Agent JSONL。
// Created on 2026-11-01; Updated on 2026-11-01
// @author: https://github.com/Linmoqian
use serde_json::Value;
use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
};
use tauri::ipc::Channel;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[derive(Clone, Default)]
pub struct AgentProcesses(Arc<Mutex<HashMap<String, Option<Arc<Mutex<Child>>>>>>);

impl AgentProcesses {
    pub fn stop_all(&self) {
        if let Ok(mut processes) = self.0.lock() {
            for (_, process) in processes.drain() {
                if let Some(process) = process {
                    if let Ok(mut child) = process.lock() { let _ = child.kill(); }
                }
            }
        }
    }
}

fn core_directory() -> Result<PathBuf, String> {
    let path = std::env::var_os("XIAOXIA_CORE_DIR").map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../core"));
    let path = path.canonicalize().map_err(|_| "找不到 core，请配置 XIAOXIA_CORE_DIR".to_string())?;
    if !path.join("src/xiaoxia_core/agent/bridge.py").is_file() {
        return Err("core 中缺少 Agent 桥接模块".into());
    }
    Ok(path)
}

fn python_executable() -> PathBuf {
    if let Some(path) = std::env::var_os("XIAOXIA_PYTHON") { return path.into(); }
    if let Some(home) = std::env::var_os("USERPROFILE") {
        let base = PathBuf::from(home).join("Anaconda3/python.exe");
        if base.is_file() { return base; }
    }
    PathBuf::from("python")
}

#[tauri::command]
pub async fn agent_request(
    request_id: String, request: Value, on_event: Channel<Value>,
    state: tauri::State<'_, AgentProcesses>,
) -> Result<(), String> {
    let state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let core = core_directory()?;
        let mut command = Command::new(python_executable());
        let mut paths = vec![core.join("src")];
        if let Some(existing) = std::env::var_os("PYTHONPATH") { paths.extend(std::env::split_paths(&existing)); }
        command.args(["-u", "-m", "xiaoxia_core.agent.bridge"])
            .current_dir(&core)
            .env("PYTHONPATH", std::env::join_paths(paths).map_err(|e| e.to_string())?)
            .env("PYTHONIOENCODING", "utf-8")
            .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
        #[cfg(windows)]
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        let mut registry = state.0.lock().map_err(|_| "Agent 进程表不可用")?;
        if let Some(existing) = registry.get(&request_id) {
            if existing.is_none() {
                registry.remove(&request_id);
                return Err("请求已取消".into());
            }
            return Err("请求 ID 已存在".into());
        }
        let mut child = command.spawn().map_err(|e| format!("无法启动 base Python: {e}"))?;
        let stdout = child.stdout.take().ok_or("无法读取 Agent 输出")?;
        let mut input = child.stdin.take().ok_or("无法写入 Agent 输入")?;
        let process = Arc::new(Mutex::new(child));
        registry.insert(request_id.clone(), Some(process.clone()));
        drop(registry);
        let outcome = (|| -> Result<(), String> {
            writeln!(input, "{}", request).map_err(|e| e.to_string())?;
            drop(input);
            for line in BufReader::new(stdout).lines() {
                let line = line.map_err(|e| e.to_string())?;
                if line.trim().is_empty() { continue; }
                let event = serde_json::from_str::<Value>(&line)
                    .map_err(|_| "Agent 返回了无法识别的消息".to_string())?;
                on_event.send(event).map_err(|_| "聊天窗口已关闭".to_string())?;
            }
            Ok(())
        })();
        // 不在阻塞读取或等待退出期间持有全局锁，允许前端随时停止。
        let status = {
            let mut child = process.lock().map_err(|_| "Agent 子进程不可用")?;
            if outcome.is_err() { let _ = child.kill(); }
            child.wait().map_err(|e| e.to_string())?
        };
        if let Ok(mut registry) = state.0.lock() { registry.remove(&request_id); }
        outcome?;
        if !status.success() { return Err("Agent 进程已停止或运行失败".into()); }
        Ok(())
    }).await.map_err(|e| e.to_string())?
}

#[tauri::command]
pub fn agent_cancel(request_id: String, state: tauri::State<'_, AgentProcesses>) -> Result<(), String> {
    let process = state.inner().0.lock().map_err(|_| "Agent 进程表不可用")?
        .entry(request_id).or_insert(None).clone();
    if let Some(process) = process {
        process.lock().map_err(|_| "Agent 子进程不可用")?.kill().map_err(|e| e.to_string())?;
    }
    Ok(())
}

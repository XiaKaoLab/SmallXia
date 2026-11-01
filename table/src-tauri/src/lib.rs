// 功能：启动机械臂 Tauri 窗口。
// Created on 2026-11-01; Updated on 2026-11-01
// @author: https://github.com/Linmoqian
mod agent;
mod debug;
use tauri::Manager;
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(agent::AgentProcesses::default())
        .invoke_handler(tauri::generate_handler![agent::agent_request, agent::agent_cancel, debug::debug_webview_screenshot])
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                window.state::<agent::AgentProcesses>().stop_all();
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to run table");
}

// 功能：启动机械臂 Tauri 窗口。
// Created on 2026-11-01; Updated on 2026-11-01
// @author: https://github.com/Linmoqian
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("failed to run table");
}

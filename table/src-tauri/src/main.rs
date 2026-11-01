// 功能：应用入口与开发配置。
// Created on 2026-11-01; Updated on 2026-11-01
// @author: https://github.com/Linmoqian
// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    table_lib::run()
}


// 功能：应用入口与开发配置。
// Created on 2026-11-01; Updated on 2026-11-01
// @author: https://github.com/Linmoqian
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { installWebViewDebug } from "./debug/WebViewDebug";

installWebViewDebug();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);


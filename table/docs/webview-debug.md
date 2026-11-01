# WebView 开发调试接口

仅开发前端提供 `window.tableDebug`，不注册到 MCP，不影响 Agent 工具列表。截图命令还要求 Windows Rust debug 构建；release 调用返回错误。没有新增 HTTP 监听端口。

启动 Tauri 开发模式，在 WebView DevTools 的 Console 中调用：

```javascript
// 按唯一 CSS 选择器替换内容；支持 React 受控 input/textarea，不自动提交。
await window.tableDebug.fillInput('#chat-message-input', '测试消息');

// 也可以使用现有可访问性标签。
await window.tableDebug.fillInput('textarea[aria-label="发送消息给小虾"]', '你好');

// 捕获当前 WebView 可见区域，返回 { dataUrl, mimeType, width, height }。
const screenshot = await window.tableDebug.screenshot();

// 触发 PNG 下载（保存位置由 WebView 下载行为决定）。
await window.tableDebug.screenshot({ download: true });

// 底层原生接口（返回 PNG base64）。
// await invoke('debug_webview_screenshot');
```

`fillInput` 要求唯一匹配、可见且可编辑的 input/textarea；拒绝只读、禁用、不可见、非文本类型及超过 maxLength 的值。通过原生 value setter 与 input/change 事件同步 React，等待两帧后校验填写结果。没有模拟 Enter、点击发送或自动提交。

`screenshot` 通过 WebView2 原生 CapturePreview 获取 PNG，包含模型画布和当前页面内容，不包含系统桌面、标题栏、DevTools 或滚动区域外内容。需要窗口可见且未最小化；普通浏览器下不提供截图。Rust 捕获回调最长等待 5 秒，PNG 上限 32 MiB；界面未加载或系统捕获异常时返回错误。没有使用 DOM 重绘近似截图，也不需要修改 Three.js 渲染缓冲设置。

接口位于 `src/debug/WebViewDebug.ts`，原生捕获位于 `src-tauri/src/debug.rs`。React 聊天输入框增加稳定 ID `chat-message-input`，未改变布局。

本次只同步 Cargo 锁文件并检查 Git 差异，没有执行构建、运行桌面或实际填写/截图验证。

原生捕获接口参考 [Microsoft WebView2 CapturePreview](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2#capturepreview)。


## 管理积木

通过 `window.tableDebug.blocks` 管理当前左侧工作区。只在开发模式注册，普通浏览器开发模式也能使用；无需启动模型 API，修改积木不会自动运行 Python。

```javascript
const blocks = window.tableDebug.blocks;
blocks.ready();                           // 工作区是否完成初始化
blocks.types();                           // 支持的类型、字段、模型限位
const [block] = blocks.list();             // 查询 ID、类型、六轴字段和坐标
blocks.setFields(block.id, { shoulder_pan: 0.2, gripper: 0.5 });
blocks.move(block.id, 24, 40);              // 工作区绝对坐标
const python = blocks.python();            // 即时生成当前 Python
const snapshot = blocks.exportWorkspace(); // { version: 1, blocks: [...] }
blocks.remove(block.id);                   // 按 ID 删除，不发送动作
blocks.create({ shoulder_pan: 0.3 });       // 空工作区添加位置积木，其他轴取默认值
blocks.clear();                            // 清空，不发送动作
blocks.importWorkspace(snapshot);          // 替换为此前保存的快照
blocks.importWorkspace(JSON.stringify(snapshot)); // 也支持 JSON 字符串
```

当前仅支持一个 `table_set_arm_position` 积木。新增前需清空或删除现有积木。字段名沿用六轴 API：`shoulder_pan`、`shoulder_lift`、`elbow_flex`、`wrist_flex`、`wrist_roll`、`gripper`，单位 rad。字段修改支持部分更新，但非法字段或越界值会在修改前拒绝，不静默截断；导入快照要求完整六轴字段，校验通过后才替换工作区。

每次管理操作同步触发 Python 预览刷新；清空后代码为空，运行按钮禁用。工作区卸载后解除绑定，接口抛出明确的未就绪错误，避免继续操作旧工作区。UI 默认积木不可手动删除，开发接口可显式删除。

本次只做代码差异检查，未构建或实际操作 WebView 验证。

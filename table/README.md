# Table

Tauri 2 + React + TypeScript + Vite。界面仅显示本地 SO-ARM-101 URDF 模型，鼠标拖动旋转、滚轮缩放。

```powershell
cd C:\Users\30470\.codex\worktrees\xiaoxia-fresh-start\小虾台\table
pnpm install
pnpm tauri dev
```

包管理使用 pnpm，依赖版本记录在 pnpm-lock.yaml 和 src-tauri/Cargo.lock。模型来源和许可证见 public/robots/so101/SOURCE.md。

尚未构建或启动桌面程序；WebView2、编译工具链和模型实际显示效果有待首次运行确认。

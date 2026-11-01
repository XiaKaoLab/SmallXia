# 机械臂位置积木

左侧采用 Blockly 13.4.0，提供“设置机械臂位置”和“装配虚拟相机”积木，每种最多一个。六轴绝对角度单位为 rad，数值范围直接读取 table 当前 SO101 URDF；模型服务可用且用户未编辑时，从当前显示目标初始化，否则使用范围内的零位。

Python 通过 Blockly Python generator 在后台生成，界面不展示代码，也不提供复制和下载控件。顶部绿色运行按钮使用现有 Conda base 执行生成结果。开发时仍可通过 `window.tableDebug.blocks.python()` 获取代码。脚本仅用 Python 标准库，通过 POST `/api/v1/robots/table/motions` 调用本机模型 API，令牌从 `XIAOXIA_MOTION_TOKEN` 读取。运行前按 core 的 motion-api 文档启动模型服务，并打开 table。

```powershell
$env:XIAOXIA_MOTION_TOKEN = "与模型服务一致的令牌"
& C:\Users\30470\Anaconda3\python.exe .\set_arm_position.py
```

编辑积木不会自动发送指令。顶部右侧绿色播放按钮通过现有 Tauri/Python 桥接执行当前生成的 Python，并调用模型 API；运行中禁用重复点击，底部显示回执或错误。执行超时为 5 秒，使用现有 base，不需要 OpenAI 配置。运行入口执行本地 Python 代码，当前来源为积木生成结果；不应连接不受信的远程页面。普通浏览器仅支持编辑与导出，运行需要 Tauri 桌面。API accepted 表示目标已接收，不能当作模型到位或实机反馈。

`public/blockly-media` 来自已安装的 Blockly 13.4.0 npm 包，保留上游 LICENSE，供离线图标及光标资源使用。生成语言保持 Python，不展示代码。

实现参考 [Blockly 自定义积木生成器](https://docs.blockly.com/guides/create-custom-blocks/code-generation/block-code/)。本次未构建或启动桌面，视觉效果与 API 联动尚未运行验收。


## 装配虚拟相机

点击左侧顶部“相机”添加积木，选择安装连杆，填写局部 X/Y/Z（米）、Roll/Pitch/Yaw（弧度）、垂直视场角（10～140 度），再点绿色运行按钮。位置范围为 ±2 米，旋转为 ±π；该范围仅是参数保护，不代表碰撞或安装可行性验证。

Python 通过 POST `/api/v1/robots/table/camera` 提交 `{parent_link, position:[x,y,z], rotation:[roll,pitch,yaw], fov}`。令牌沿用 `XIAOXIA_MOTION_TOKEN`。同一台虚拟相机重复运行只更新装配，不重复叠加。GET state 的 camera 字段返回当前配置；服务重启不持久保存相机配置，需重新运行积木。

模型将相机外形和视锥挂在所选 URDF 连杆下，随连杆运动；旋转顺序为 Rz(yaw)Ry(pitch)Rx(roll)，镜头光轴为局部 -Z。当前仅显示装配及视锥，没有新增相机画面预览或图像采集，不访问 USB 相机。

本次完成 TypeScript 无输出类型检查、Python 语法检查，并确认当前 WebView 中出现新积木类型和相机按钮。未执行虚拟相机装配后的视觉验收，未构建桌面安装包。

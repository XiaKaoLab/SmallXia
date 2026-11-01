# Table

Tauri 2 + React + TypeScript + Vite。左侧是本地 SO-ARM-101 URDF 模型，右侧是半透明聊天栏，默认桌面窗口按 3:1 分配宽度。聊天支持会话切换、技能选择、Markdown 回复、流式文本、复制和停止生成。

```powershell
conda activate base
cd 'C:\Users\30470\.codex\worktrees\xiaoxia-fresh-start\小虾台\table'
$env:OPENAI_API_KEY = '你的密钥'
$env:OPENAI_MODEL = '你有访问权限的模型名称'
pnpm install
pnpm tauri dev
```

包管理使用 pnpm，依赖版本记录在 pnpm-lock.yaml 和 src-tauri/Cargo.lock。模型来源和许可证见 public/robots/so101/SOURCE.md。

前端新增 Motion（动效与 reduced-motion）、React Router（Hash 路由与会话 URL）、Lucide React（轻量线性图标）、React Markdown 和 remark-gfm。屏幕宽度 ≤1000px 时聊天栏保持 320px，极窄屏改为上下布局；默认 1440px 桌面窗口的聊天栏为 360px。

桌面通信采用 Tauri Channel → 隐藏的 Python 子进程 → `xiaoxia_core.agent.bridge`，使用已有 `base`，不新建 HTTP 服务。默认查找用户目录下 `Anaconda3/python.exe`，可用 `XIAOXIA_PYTHON` 指定 Python 路径。开发模式按仓库布局定位 `core`；换位置时设置 `XIAOXIA_CORE_DIR` 为含 `src` 和 `skills` 的 core 绝对路径。Python 继承启动桌面程序时的模型和密钥环境变量，前端不接收密钥。

会话与核心 CLI 共用 `core/data/agent.sqlite3`，停止生成会终止该轮 Python 进程。后端 `completed` 事件表示该轮已保存；失败或中止的预览会标注状态。停止与响应完成若发生竞争，以恢复后的数据库历史为准。`skill_loaded` 显示为真实技能卡片。工具卡片支持 `tool_started/tool_delta/tool_completed` 前端事件，但当前简单 Agent 尚未发出工具事件，不展示虚构调用。恢复历史时只恢复后端已保存的文本，不恢复技能/工具活动卡片。

普通浏览器可查看界面和模型，聊天会提示使用桌面应用。当前桌面桥接面向本地源码开发；发布安装包时仍需独立部署 core/base 并配置路径，尚未打包 Python 运行时。

本次未构建、未启动桌面程序、未调用模型 API；实际排版、桌面桥接与端到端聊天仍待运行确认。


## 积木分类

左侧使用 Blockly 分类工具箱：机械臂、相机、逻辑、变量、策略、数据。点击分类后拖入积木；顶部绿色按钮运行 Python，界面不显示源码。

- 机械臂：六轴角度滑杆，保留实时模型预览。
- 相机：固定装配相机、获取虚拟或真实画面。
- 逻辑：条件分支、比较、与/或、非、布尔值和条件取值。
- 变量：创建变量、赋值/读取、画面变量、文本与数字。
- 策略：训练、预测、table 回放、查询和停止后台任务；使用 core 模仿学习 API。

策略积木接受 ID 文本或保存的任务响应变量；训练/预测/回放返回异步任务对象，可通过变量保存，再使用任务状态查询。依赖任务需成功后再发起下一步，未自动等待训练完成。

开发接口工作区导出使用 version=2 原生序列化，保留变量和嵌套连接；导入仍接受旧 version=1 平铺快照。

“数据”分类提供仿真/真机只读采集创建、启动、逐帧记录、保存回合、结束/停止、会话与命令状态积木，调用 core collection API。创建/命令返回对象通过变量保存；异步回执需查询，不会等待整段采集结束。

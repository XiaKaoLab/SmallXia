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


## 装配相机

点击左侧顶部“相机”按钮添加“装配相机”积木。积木只有名称，没有安装连杆、显示开关、XYZ、旋转或视场角输入。使用 cameraBlock.ts 的固定 CAMERA_PRESET，运行时由后台 Python 调用相机 API。

固定挂在 gripper_link，偏移为 (0.03, 0, -0.015) m、旋转 (0, 0, 0) rad、FOV 60°；安装支架使用上游 STL。光心偏移和镜头参数仍是显示示意，不是实测标定。

只有将“装配相机”积木加入工作区并点击绿色运行，才提交显示相机和虚拟画面的请求。编辑或添加积木本身不发送请求，未执行装配时默认隐藏。重复运行更新同一相机。

## 文档安装位置与按需显示

上游固定版本 [腕部相机装配指南](https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/Optional/Wrist_Cam_Mount_32x32_UVC_Module/README.md) 说明，用带相机孔位的支架替换 Wrist Roll，安装 32×32 mm 模组。当前 URDF 的 wrist_roll 关节连接 wrist_link → gripper_link，因此模型默认挂载到 gripper_link，随腕部旋转，不挂到活动夹爪。

指南没有提供相机光心相对 URDF 的精确 XYZ/RPY 或标定外参。默认局部偏移 `(0.03, 0, -0.015)` m、旋转 `(0, 0, 0)` rad 只是可编辑的显示示意；镜头朝局部 -Z，接近 gripper_frame_link 所在方向。它们不能作为文档测量值或真实手眼标定值。FOV 60° 也是显示参数。

“装配相机”积木的运行即显式显示请求，API 提交 visible=true，在模型区右下角创建 4:3 实时虚拟画面；底层 visible=false 仍可隐藏并释放预览资源，积木不再暴露此开关。


## URDF 缺失时使用 STL 支架

已引入固定上游版本的 SO101 一体式腕部相机支架 STL，文件为 `public/robots/so101/camera/wrist_camera_mount_so101.stl`。相机显式显示时，若 URDF 没有相机支架引用，则用它替换 `gripper_link` 下原腕部打印件的视觉网格；其余舵机和活动夹爪保持原样。隐藏相机时恢复原网格。未修改碰撞体或动力学模型。

STL 坐标按毫米缩放至米，沿用原打印件 visual 变换，不重新居中；原点与主要主体边界相符。支架是实际 CAD，镜头/外壳仍是示意，光心、FOV 和安装位姿仍不能作为实测外参。来源、SHA256 和几何边界已记录于相机资源目录的 provenance.json。

完成 TypeScript 类型检查；尚未开启相机进行视觉对齐验收。


## 电机角度滑杆

位置积木改用 M1～M6 内嵌滑杆，显示角度（°），内部字段与 API 仍存弧度，范围读取 URDF。用户拖动时立即调整模型对应关节，不经过原来的 0.25 rad/s 追踪；后台在 120 ms 静默间隔后合并最新位置程序，通过现有 base Python/API 同步完整六轴目标。只运行位置积木代码，不顺带执行相机装配。请求串行发送，较新本地角度不会被较旧 API 轮询覆盖。API 失败时保留本地预览并提示失败；不会控制串口或实机。

绿色运行按钮继续执行整个积木工作区，并与后台位置队列串行协调。已完成类型检查，并在当前 WebView 将 M1 调整到 30°，读取 API 确认 0.5235987756 rad，其他五轴目标未变。


## 碰撞前停止

角度范围之外增加整臂姿态约束。滑杆沿当前姿态向目标按最大 1° 关节步长检查；遇到非相邻连杆表面交叉，或视觉包围盒低于底座底平面 1 mm 时，二分细化边界并停在最后可用位置，滑杆回显实际角度。原始 URDF 视觉网格用 three-mesh-bvh 做窄相检查，排除同连杆和直接相邻连杆的机械连接。加载完成前不允许移动；使用网格完成回调避免 StrictMode 请求去重导致过早初始化。

API 使用既有 MuJoCo 导入的碰撞网格凸包检查自碰撞，并沿线性关节路径按最大 1° 步长检查与二分细化。碰撞目标仍返回 accepted，但响应增加 applied_joint_positions、limited、limit_reason；关节范围非法值继续返回参数错误。模型服务只提交边界前的目标。滑杆收到较保守的 API 修正时同步回显，带修改版本号防止覆盖更新的拖动。

这是显示模型的离散碰撞保护，不是实机安全认证或连续碰撞检测。MuJoCo 凸包可能保守，前端地平面使用包围盒；接触容差约 0.5～1 mm，不能解释为精确零距离。未对可选相机支架、桌面物体和线缆建立碰撞模型，直接相邻连杆干涉也不在此检查范围。

已确认原截图角度在 URDF 范围内，但存在底座与下臂、腕部、夹爪的碰撞。零位和小幅姿态通过；同一重叠目标在 API 检查中会截断。当前 WebView 将 M2 从约 17.19° 拖向 100° 时停在约 47.02°，API 读回 0.8206311 rad。边界取决于其余五轴姿态，不是 M2 的固定角度限位。

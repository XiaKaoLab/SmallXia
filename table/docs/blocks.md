# 机械臂位置积木

左侧采用 Blockly 13.4.0，仅提供“设置机械臂位置”积木。六轴绝对角度单位为 rad，数值范围直接读取 table 当前 SO101 URDF；模型服务可用且用户未编辑时，从当前显示目标初始化，否则使用范围内的零位。

下方预览通过 Blockly Python generator 生成的完整 Python。可以复制或下载 `set_arm_position.py`，在现有 Conda base 中运行。脚本仅用 Python 标准库，通过 POST `/api/v1/robots/table/motions` 调用本机模型 API，令牌从 `XIAOXIA_MOTION_TOKEN` 读取。运行前按 core 的 motion-api 文档启动模型服务，并打开 table。

```powershell
$env:XIAOXIA_MOTION_TOKEN = "与模型服务一致的令牌"
& C:\Users\30470\Anaconda3\python.exe .\set_arm_position.py
```

编辑积木不会自动发送指令；当前侧栏提供代码生成和导出，未增加内嵌 Python 执行器。API accepted 表示目标已接收，不能当作模型到位或实机反馈。

`public/blockly-media` 来自已安装的 Blockly 13.4.0 npm 包，保留上游 LICENSE，供离线图标及光标资源使用。没有增加其他内置积木或生成语言。

实现参考 [Blockly 自定义积木生成器](https://docs.blockly.com/guides/create-custom-blocks/code-generation/block-code/)。本次未构建或启动桌面，视觉效果与 API 联动尚未运行验收。

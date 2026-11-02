# 真实相机内参标定

Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian

在“相机”分类拖入“标定真实相机”，选择实际发现的摄像头。默认 9×6 个内角点、25 mm 方格，运行后打开标定窗口。可下载按毫米定义的 SVG 棋盘格，默认版面 280×205 mm；打印必须关闭缩放，并实测方格边长。其他尺寸可能需要更大纸张。

固定相机焦距、对焦与采集分辨率，将平整标定板置于不同位置、距离和倾角，完整角点识别后点击“采集此帧”。至少 12 帧，建议 20 帧以上并覆盖画面边缘。重复样本、棋盘格过小、未找到完整角点或分辨率改变会被拒绝。更换相机、镜头、焦距或分辨率后不要直接复用旧参数。

点击“计算并保存”获得 3×3 K、五项 Brown–Conrady 畸变参数（k1/k2/p1/p2/k3）、实际图像尺寸、总 RMS 和逐帧 RMS。覆盖位置不足、倾角不足、主点异常或 RMS 超过 1 px 时给出 needs_review，不把低训练误差当作独立验收。结果可导出 JSON，当前窗口按匹配分辨率展示去畸变预览。原始真实画面 API 不自动改成去畸变图像。

数据保存在 `core/data/camera_calibration/sessions.sqlite3`，每会话目录保存采集 JPEG 和 `intrinsics.json`。增加样本会使旧结果失效，需重新计算。关闭窗口停止标定预览，样本仍保留。内参不包含相机到机械臂的外参或手眼标定。

复用现有相机服务 `GET /api/v1/cameras/{camera_id}/frame` 与认证，不新增独立相机采集连接，不需重启当前训练或模型服务。真实帧来自现有相机服务的 JPEG，实际分辨率写入结果。相机服务共享设备连接；标定期间不要在其他流程切换摄像头。

桌面桥接口：

- `camera_calibration_action`，`operation=start`：传 `camera_id`、`columns`、`rows`、`square_mm`，返回会话 `id`。
- 同动作 `operation=get/capture/solve`：传 `session_id`。get 返回样本数和当前结果，capture 采集一帧，solve 计算并持久化结果。
- `camera_calibration_preview`：传 `session_id`，通过 calibration 事件输出角点预览与状态；关闭窗口取消该流。
- 积木类型 `table_calibrate_camera`，字段 SOURCE/COLUMNS/ROWS/SQUARE_MM，生成 Python 调用 `CameraCalibration.start`，通过 camera_calibration 回执打开现有 WebView。

采用 OpenCV 棋盘格检测和 calibrateCamera： https://docs.opencv.org/4.10.0/d9/d0c/group__calib3d.html 。

验证范围见 camera-calibration-check.json：24 个已知内参的合成视角 RMS 约 0.110 px；生成棋盘格识别 54 个角点；临时合成夹具验证持久化、重复样本拒绝和虚拟相机拒绝。WebView 可见新积木及真实相机选项。没有采集用户的真实标定板，不宣称真实相机已完成标定；没有执行完整构建。

# 红色物体跟随

Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian

相机分类新增“跟踪红色物体”。检测不限圆形，支持红色方块等区域。目标为画面居中，不估算深度、不接近或抓取物体。

真机积木顺序：使能机械臂 COM17 → 跟踪红色物体（目标 COM17、选择真实相机）→ 失能机械臂 COM17。相机须安装在机械臂上并随其运动；固定外部相机不适合此朝向跟随方式。仿真先运行相机积木，目标选仿真、相机选腕部虚拟相机。

时长 0 表示持续跟随，点击停止结束。指定时长可自动衔接后续积木。只调整肩部旋转和腕部弯曲，其他关节保持；默认方向可用“水平反向／垂直反向”适配安装方向。此基础控制假定图像水平、垂直分别主要对应这两个关节，任意姿态或相机旋转下的轴耦合尚未标定。

双红色色域阈值、形态学去噪和邻近目标关联用于检测；中心位置低通平滑并设置画面中心 4% 死区。跟随目标速度最高 0.12 rad/s，沿用机械臂的加减速轨迹。目标丢失时下发当前位置作为保持目标，不沿旧方向追赶；同一虚拟相机帧不重复驱动。画面中的目标框复用已有相机窗口，不新增第二个窗口。

Python API：

```python
from xiaoxia_core.communication.hardware_client import HardwareClient
from xiaoxia_core.blocks.red_tracking import RedObjectTracker

arm = HardwareClient('COM17')
try:
    arm.enable()
    RedObjectTracker().run(target='serial:COM17', camera='opencv_设备标识', seconds=30)
finally:
    arm.disable()
```

`run` 支持 `horizontal=1/-1`、`vertical=1/-1`、`stop_event=threading.Event()`。使用已发现相机的稳定 `opencv_…` 标识；`real` 别名需要已配置默认真实相机。真机模式不接受虚拟图像，不自动连接使能。错误会请求回位失能；正常结束先保持当前位置，供后续积木衔接。积木程序停止仍沿用返回起始位置后失能的清理流程。

颜色检测会受光照、反光和其他红色物体影响；本功能未验收真机跟随效果，也不代表抓取成功。

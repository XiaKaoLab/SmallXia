# 按文字抓取方块

Created on 2026-11-03; Updated on 2026-11-03  
@author: https://github.com/Linmoqian

流程是 OCR 读字 → 唯一匹配目标 → 标定定位 → 共用抓取策略。文字不作为动作模型的分类标签，不为每个新字重新训练动作。

## 当前入口

- 相机积木「识别文字」：选择已发现的相机，返回文字、像素框、置信度与真实/虚拟来源。只读，不运动。
- 策略积木「仿真抓取文字方块」：输入目标文字、选择已有 ONNX 抓取模型及轮数。仿真自动摆放三个包含目标文字的方块，随机换位后识别与抓取。
- Agent 工具 `rl_read_text` 和 `rl_pick_text_simulation` 提供同样能力。
- `POST /api/v1/vision/text-recognitions`：`camera_id`、可选 `target_text`。
- `POST /api/v1/vision/text-picks`：`target_text`、`model_job_id`、可选 `texts`（三个互不相同的文字）、`rounds`、`seed`、`playback_speed`。
- `GET /api/v1/vision/capabilities` 查询范围。
- 仿真任务复用 `/api/v1/reinforcement/jobs/{id}` 查询、暂停、继续和停止。

HTTP 沿用本机 Bearer 令牌。Python 可使用既有 `BlockWorkflow.http`，不需要把令牌写进程序。

```python
from xiaoxia_core.blocks.workflow import BlockWorkflow
job = BlockWorkflow.http('vision/text-picks', {
    'target_text': '苹果',
    'texts': ['苹果', '香蕉', '橙子'],
    'model_job_id': 'latest',
    'rounds': 1,
    'seed': 2026,
})
BlockWorkflow().wait_job(job, 'reinforcement')
```

首次安装使用核心包的 `text-vision` 可选依赖。RapidOCR 自带 ONNX OCR 模型；无需训练 ABC 分类器。支持范围由 OCR 的语言、字体、分辨率及遮挡情况决定，不承诺任意文字必然识别。

当前版本针对固定规格文字方块和明确印刷文字。文字匹配使用 NFKC、忽略大小写及空白；目标缺失、重复或低置信度时不发送抓取动作。1.2.3 解码器的置信度均值含额外近零样本，适配层移除此项，同时返回原始分数。

## 已完成的验证与边界

2026-11-03 在「苹果／香蕉／橙子」随机摆位场景中，OCR 识别苹果，按相机内外参与方块顶面高度求交定位，调用已有抓球 ONNX 完成一次方块夹持抬升，保持约 1.18 秒。分类、定位、选中物体和抓取结果分别保存。

视觉选择只读图像，不把物体名称提供给 OCR；仿真中的刚体名称仅用于控制器绑定及验收。已有抓取控制器仍接收仿真辅助状态，因此这不是纯视觉端到端策略，也不是实机抓取验证。相同文字在不同规格、摩擦或姿态的方块上，抓取仍需单独验收。

真实相机入口只读图像。真实坐标定位还需要匹配该相机的内外参、去畸变及桌面/深度信息，不能复用仿真相机外参；当前未开放真实机械臂自动抓取。

## 相机分辨率

文字选择使用独立的 1024×1024 仿真俯视 RGB，界面显示同一来源的画面，可展开查看。用于定位的内参按实际分辨率计算。已有 ONNX 抓取策略继续接收原来的 64×64 腕部图像，未通过插值伪造高分辨率策略输入。普通虚拟腕部预览以 960×720 原生渲染。

OCR 与动作模型各自使用不同的相机输入，界面标题及预览元数据显式包含来源和分辨率。真实相机硬件分辨率未在此修改；应以设备实际返回帧尺寸为准。

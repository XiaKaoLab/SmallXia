# SO-100 显示模型

来源为 TheRobotStudio/SO-ARM100 的 Simulation/SO100，固定提交 a758567c3978dfeefe282ede0500085a48fe8f78，Apache-2.0。

原始 so100.urdf、13 个 STL 和 profile.json 取自本机 2026-11-01 项目备份，复制前逐文件核对 profile.json 中的 SHA-256。网络原始下载失败后复用缓存；本次未重新从上游下载二进制网格。原始文件保持不变。

so100_mid_calib.urdf 由 core/scripts/prepare_so100.py 生成：五轴 origin 右乘绕自身 axis 的原始行程中值旋转，并将 limit 同量平移，使 0 表示原行程中点；不缩放角度，不改变几何或可达姿态。夹爪保留闭合零位，连杆使用应用统一的 *_link 命名。此约定不等同于对每个实机安装误差的测量。

默认查看器、运动路由、碰撞检查、积木限位、MCP 限位和仿真采集均使用该 SO-100 文件。已有 SO-101 抓球模型仍保留原来的物理环境及独立前端模型，未重训或迁移其权重。SO-101 专用相机支架不会套用到 SO-100 的打印件。

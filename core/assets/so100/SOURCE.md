# SO-100 模型来源

- 上游：[TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100)
- 固定提交：`a758567c3978dfeefe282ede0500085a48fe8f78`
- 路径：`Simulation/SO100/so100.urdf` 与其引用的 13 个 STL。
- 恢复入口：`core/scripts/restore_so100.py`。GitHub 传输失败时使用同提交的 jsDelivr 镜像；本地资源 SHA256 记录在 `provenance.json`。
- 许可证：同目录 `LICENSE`，保留上游原版 URDF 和网格。

URDF 限位用于模型约束，不能替代当前设备的机械限位测量。上游 `effort=35` 不是本项目确认的 STS3215 实际可用扭矩。MuJoCo 导入适配只在内存中处理中文路径、固定底座与直接相邻 link 的接触排除，原始 URDF 不做改写。

# 来源

https://hugging-face.cn/docs/lerobot/feetech

# Feetech 电机固件更新

本教程将引导您使用 Feetech 官方软件更新 Feetech 电机的固件。

## 先决条件

* Windows 计算机（Feetech 软件仅适用于 Windows）
* Feetech 电机控制板
* 用于将控制板连接到计算机的 USB 数据线
* 连接到控制板的 Feetech 电机

## 步骤 1：下载 Feetech 软件

1. 访问 Feetech 官方软件下载页面：<https://www.feetechrc.com/software.html>
2. 下载最新版本的 Feetech 调试软件 (FD)
3. 在您的 Windows 计算机上安装该软件

## 步骤 2：硬件设置

1. 将 Feetech 电机连接到电机控制板
2. 通过 USB 数据线将电机控制板连接到 Windows 计算机
3. 确保电机已接通电源

## 步骤 3：配置连接

1. 启动 Feetech 调试软件
2. 从端口下拉菜单中选择正确的 COM 端口
   * 如果不确定使用哪个端口，请检查 Windows 设备管理器中的“端口 (COM 和 LPT)”
3. 设置适当的波特率（大多数 Feetech 电机通常为 1000000）
4. 点击 “Open” 以建立与控制板的通信

## 步骤 4：扫描电机

1. 连接成功后，点击 “Search” 按钮以检测所有连接的电机
2. 软件将自动发现并列出总线上的所有电机
3. 每个电机将与其 ID 编号一起显示

## 步骤 5：更新固件

对于每个需要更新的电机：

1. 通过点击列表中的**电机来选择它**
2. **点击 Upgrade 选项卡**:
3. **点击 Online 按钮**:
   * 如果发现潜在的固件更新，它将显示在方框中
4. **点击 Upgrade 按钮**:
   * 界面将显示更新进度

## 步骤 6：验证更新

1. 更新完成后，软件应自动刷新电机信息
2. 确认固件版本已更新至预期版本

## 重要提示

⚠️ **警告**：在固件更新期间请勿断开电源或 USB 连接，否则可能会导致电机损坏（变砖）。

## 额外内容：在 Linux/macOS 上进行电机调试

仅用于调试目的，您可以使用开源的 Feetech Debug Tool

* **仓库**：[FT\_SCServo\_Debug\_Qt](https://github.com/CarolinePascal/FT_SCServo_Debug_Qt/tree/fix/port-search-timer)

### 安装说明

请按照仓库中的说明安装工具。对于 Ubuntu，您可以直接安装；对于 MacOS，您需要从源代码构建。

**局限性**

* 该工具仅用于调试和参数调整
* 固件更新仍必须在 Windows 上使用 Feetech 官方软件完成

 [在 GitHub 上更新](https://github.com/huggingface/lerobot/blob/main/docs/source/feetech.mdx)
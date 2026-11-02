/** 功能：将界面错误转换为简短、可操作的提示，保留原始异常供调用方处理。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
export class UiMessage {
  static error(value: unknown, fallback = "操作失败，请重试"): string {
    const message = String(value ?? "").replace(/^(Error:\s*)+/, "").trim();
    if (!message) return fallback;
    const rules: [RegExp, string][] = [
      [/跨圈/, "编码器跨圈，请重新采集"],
      [/行程不足|same min and max/, "部分关节行程不足，请继续转动"],
      [/力矩/, "请关闭机械臂力矩"],
      [/校准.*不一致|校准.*不匹配|校准.*变化/, "校准不匹配，请重新校准"],
      [/校准.*恢复.*失败/, "校准恢复失败，请检查设备"],
      [/未识别.*棋盘格/, "未识别标定板，请调整位置"],
      [/标定板太小/, "请靠近相机"],
      [/已有样本过于相似/, "画面重复，请移动标定板"],
      [/分辨率发生变化/, "分辨率已改变，请重新标定"],
      [/重投影误差/, "误差偏大，请重新采集"],
      [/覆盖区域不足/, "请补充画面边缘的样本"],
      [/倾角变化不足/, "请增加标定板倾角"],
      [/主点位于画面外/, "标定异常，请重新采集"],
      [/样本.*不足|至少.*帧/, "样本不足，请继续采集"],
      [/重复.*采样|相似.*采样|重复.*帧/, "画面重复，请移动标定板"],
      [/PermissionError|Access is denied|拒绝访问|串口.*占用/, "串口被占用，请关闭其他连接"],
      [/could not open port|无法打开.*串口/, "串口不可用，请检查连接"],
      [/timeout|timed out|超时/i, "连接超时，请检查设备"],
      [/Failed to fetch|Connection refused|连接被拒绝|API.*不可用/i, "服务未连接，请重试"],
    ];
    for (const [pattern, label] of rules) if (pattern.test(message)) return label;
    const firstLine = message.split(/\r?\n/)[0];
    return firstLine.length > 64 ? fallback : firstLine;
  }
}

/** 功能：将 MCP 工具标识、协议包装与字段转换为简短中文说明。
 * Created on 2026-11-03; Updated on 2026-11-08
 * @author: https://github.com/Linmoqian
 */
const tools: Record<string, [string, string]> = {
  gesture_list: ["查看已有动作", "挥手、旋转、鞠躬等本地动作与示例"],
  gesture_play: ["运行动作编排", "按顺序执行已有动作，区分仿真与真机"],
  gesture_status: ["查看动作进度", "查询后台动作的实际状态与结果"],
  gesture_stop: ["停止动作", "结束编排并释放真机控制"],
  robot_list_cameras: ["查看摄像头", "区分真实摄像头与虚拟相机，读取设备名称和ID"],
  robot_observe: ["观察机械臂", "读取真实相机或仿真截图，标注来源身份并结合CSV分析"],
  robot_get_environment: ["查看仿真与真机", "识别机械臂串口候选并查看连接状态"],
  table_get_state: ["读取机械臂状态", "查看仿真模型当前的六轴角度"],
  table_get_limits: ["读取关节限位", "查看各关节允许的角度范围"],
  table_move_joints: ["设置机械臂姿态", "向仿真模型发送六轴目标角度"],
  blocks_catalog: ["查看积木目录", "了解可用积木及其参数"],
  blocks_list: ["读取当前积木", "查看工作区中的积木与连接"],
  blocks_create: ["添加积木", "在编程区放入指定积木"],
  blocks_set_fields: ["设置积木参数", "修改积木中的选项和数值"],
  blocks_move: ["移动积木", "调整积木在编程区的位置"],
  blocks_connect: ["连接积木", "把积木连接成程序"],
  blocks_remove: ["删除积木", "移除指定积木"],
  blocks_clear: ["清空积木", "清空当前编程区"],
  blocks_export: ["备份积木", "保存当前积木与连接"],
  blocks_import: ["恢复积木", "载入已有的积木程序"],
  blocks_run: ["运行积木程序", "提交当前程序，完成情况需查询运行状态"],
  blocks_command_status: ["查询积木操作", "确认积木操作是否完成"],
  blocks_programs: ["查看后台程序", "查看积木程序的运行情况"],
  blocks_program_status: ["查询程序进度", "读取程序的状态和输出"],
  blocks_program_stop: ["停止积木程序", "停止程序并清理它启动的任务"],
  rl_read_text: ["识别相机文字", "读取文字、位置与置信度，保留相机来源"],
  rl_pick_text_simulation: ["按文字抓取方块", "识别和定位目标文字，再运行已有抓取模型"],
  rl_train_ball: ["训练抓球策略", "在物理仿真中训练机械臂拿取小球"],
  rl_capabilities: ["查看训练能力", "读取训练环境支持的功能"],
  rl_export_onnx: ["导出 ONNX 模型", "将已训练策略导出为推理模型"],
  rl_predict_onnx: ["预测机械臂动作", "用 ONNX 模型计算下一步动作"],
  rl_rollout_onnx: ["运行 ONNX 推理", "在仿真中执行抓球策略"],
  rl_create_session: ["创建训练环境", "准备强化学习会话"],
  rl_get_session: ["读取训练环境", "查看当前会话状态"],
  rl_list_sessions: ["查看训练会话", "列出已有训练环境"],
  rl_step: ["执行训练动作", "让仿真环境前进一步"],
  rl_intervene: ["接管训练动作", "设置人工介入状态"],
  rl_feedback: ["记录任务结果", "记录本次任务成功或失败"],
  rl_label_reward: ["标注奖励", "为训练样本添加奖励标签"],
  rl_reset: ["重置训练环境", "开始新的仿真回合"],
  rl_start_learner: ["启动策略学习", "使用采集的数据更新模型"],
  rl_start_actor: ["启动策略执行", "在仿真环境中采集策略经验"],
  rl_predict: ["预测策略动作", "根据当前观测计算动作"],
  rl_train_reward: ["训练奖励模型", "学习任务奖励的判定方式"],
  rl_get_job: ["查询训练进度", "查看后台训练任务的状态"],
  rl_stop_job: ["停止训练任务", "终止指定后台任务"],
  rl_stop_session: ["关闭训练环境", "结束指定训练会话"],
};

export const jointNames: Record<string, string> = {
  shoulder_pan: "肩部旋转", shoulder_lift: "肩部抬升", elbow_flex: "肘部弯曲",
  wrist_flex: "腕部弯曲", wrist_roll: "腕部旋转", gripper: "夹爪",
};
const labels: Record<string, string> = {
  simulation: "仿真机械臂", hardware: "真机机械臂", serial_ports: "检测到的串口",
  arm_discovery: "机械臂串口判断", candidates: "候选设备", recommended_port: "推荐串口",
  confidence: "判断", evidence: "依据", manufacturer: "厂商", product: "产品",
  vid: "USB 厂商标识", pid: "USB 产品标识", serial_number: "USB 序列号",
  method: "识别方式", opened_ports: "已打开串口",
  serial_discovery: "串口查询", sessions: "控制连接", port: "串口", description: "设备说明", note: "说明",
  ...jointNames, status: "状态", id: "编号", request_id: "请求编号", robot_id: "机械臂", unit: "单位",
  joint_positions: "关节角度", applied_joint_positions: "应用角度", physical: "实机", source: "来源",
  identity: "图像身份", source_kind: "画面类型", camera_id: "相机ID", camera_name: "相机名称",
  timestamp: "采样时间", timestamp_ns: "接收时间（纳秒）", timestamp_basis: "时间依据",
  sequence: "帧序号", age_ms: "接收后间隔（毫秒）", robot_association: "机械臂归属",
  sample: "采样", view: "视角", image: "图片", csv: "CSV文件", csv_content: "CSV记录", directory: "保存位置",
  camera: "相机", playback: "回放", limited: "到达边界", limit_reason: "边界原因", lower: "下限", upper: "上限",
  command_id: "操作编号", result: "结果", program: "后台程序", kind: "任务类型", progress: "进度",
  step: "当前步数", total_steps: "总步数", frames: "帧数", episodes: "回合数", score: "分数",
  blocks: "积木", type: "类型", fields: "参数", output: "输出", error: "错误", message: "说明",
  executed: "已执行", target: "目标", model: "模型", name: "名称", position: "位置", rotation: "方向",
  visible: "显示", parent_link: "安装位置", fov: "视场角", num_envs: "并行数量", rounds: "训练轮数",
};
const values: Record<string, string> = {
  unknown: "未知", available: "可用", queried: "已查询", unavailable: "不可用", ok: "正常",
  connected: "已有控制连接", likely: "较可能", possible: "可能", metadata_and_existing_configuration: "设备信息与已有配置",
  accepted: "目标已接收", queued: "等待执行", running: "执行中", succeeded: "已完成", completed: "已完成",
  failed: "失败", cancelled: "已停止", interrupted: "已中断", paused: "已暂停", rad: "弧度",
  real_camera: "真实摄像头", simulation_render: "仿真渲染", hardware_mapped_render: "真机映射画面",
  training_render_first_environment: "训练环境画面（第一个环境）",
  core_receive_time: "后端接收时间", webview_render_capture: "前端渲染截图时间", unverified: "尚未确认",
  mapped_render: "真机映射模型", front: "正面", side: "侧面", top: "俯视",
  display_target: "仿真显示目标", table: "仿真机械臂",
};

export class ToolPresentation {
  static category(name: string): "查询" | "修改" | "运行" {
    if (["gesture_list", "gesture_status"].includes(name)) return "查询";
    if (["robot_list_cameras", "robot_observe", "robot_get_environment", "table_get_state", "table_get_limits", "blocks_catalog", "blocks_list", "blocks_export",
      "blocks_command_status", "blocks_programs", "blocks_program_status", "rl_capabilities",
      "rl_get_session", "rl_list_sessions", "rl_get_job", "rl_read_text"].includes(name)) return "查询";
    if (["table_move_joints", "blocks_create", "blocks_set_fields", "blocks_move", "blocks_connect",
      "blocks_remove", "blocks_clear", "blocks_import", "rl_create_session", "rl_intervene",
      "rl_feedback", "rl_label_reward", "rl_reset"].includes(name)) return "修改";
    return "运行";
  }
  static describe(name: string): [string, string] {
    return tools[name] ?? [name, "执行指定操作"];
  }
  static label(key: string): string { return labels[key] ?? key.replace(/_/g, " "); }
  static value(value: string): string { return values[value] ?? value; }
  static parse(output: string): unknown {
    let value: unknown = output;
    for (let depth = 0; depth < 6; depth++) {
      if (typeof value === "string") {
        try { value = JSON.parse(value); continue; } catch { return value; }
      }
      if (value && typeof value === "object" && !Array.isArray(value)) {
        const object = value as Record<string, unknown>;
        if (object.structuredContent != null) { value = object.structuredContent; continue; }
        if (Array.isArray(object.content)) {
          const texts = object.content.filter(item => item?.type === "text" && typeof item.text === "string").map(item => item.text);
          if (texts.length === 1) { value = texts[0]; continue; }
          if (texts.length > 1) return texts.map(text => ToolPresentation.parse(text));
        }
      }
      return value;
    }
    return value;
  }
}

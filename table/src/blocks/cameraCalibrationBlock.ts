/** 功能：真实相机棋盘格内参标定入口，生成现有相机 API 的 Python 调用。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator } from "blockly/python";
import { cameraCatalog } from "./CameraCatalog";

export const CAMERA_CALIBRATION_BLOCK = "table_calibrate_camera";
export function registerCameraCalibrationBlock(): void {
  Blockly.Blocks[CAMERA_CALIBRATION_BLOCK] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("标定真实相机")
        .appendField(new Blockly.FieldDropdown(function () { return cameraCatalog.realOptions(this.getValue()); }), "SOURCE");
      this.appendDummyInput().appendField("内角点 列")
        .appendField(new Blockly.FieldNumber(9, 3, 20, 1), "COLUMNS")
        .appendField("行").appendField(new Blockly.FieldNumber(6, 3, 20, 1), "ROWS");
      this.appendDummyInput().appendField("方格边长")
        .appendField(new Blockly.FieldNumber(25, 1, 200, .1), "SQUARE_MM").appendField("mm");
      this.setColour("#587e9d"); this.setPreviousStatement(true); this.setNextStatement(true);
      this.setTooltip("运行后打开真实相机标定窗口。下载棋盘格并按实际尺寸打印，从不同位置和倾角采集至少 12 帧，再计算内参与畸变系数。");
    },
  };
  pythonGenerator.forBlock[CAMERA_CALIBRATION_BLOCK] = block => {
    const source = String(block.getFieldValue("SOURCE"));
    if (!/^opencv_[0-9a-f]{16}$/.test(source)) throw new Error("请选择发现的真实相机，可在相机分类中刷新列表");
    const columns = Number(block.getFieldValue("COLUMNS"));
    const rows = Number(block.getFieldValue("ROWS"));
    const square = Number(block.getFieldValue("SQUARE_MM"));
    if (![columns, rows].every(value => Number.isInteger(value) && value >= 3 && value <= 20) || !Number.isFinite(square) || square < 1 || square > 200) throw new Error("标定板参数无效");
    return `# 功能：创建真实相机内参标定会话。\n# Created on 2026-11-02; Updated on 2026-11-02\n# @author: https://github.com/Linmoqian\nimport json\nfrom xiaoxia_core.communication.camera_calibration import CameraCalibration\nprint(json.dumps({"camera_calibration": CameraCalibration().start(${JSON.stringify(source)}, ${columns}, ${rows}, ${square})}, ensure_ascii=False))\n`;
  };
}

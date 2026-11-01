/** 功能：定义获取画面和画面变量积木，生成统一相机 API 的 Python 调用。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";
import { cameraCatalog, frameVariableName } from "./CameraCatalog";

export const FRAME_CAPTURE = "table_capture_frame";
export const FRAME_VARIABLE = "table_frame_variable";
function cameraField(): Blockly.FieldDropdown {
  return new Blockly.FieldDropdown(function () { return cameraCatalog.options(this.getValue()); });
}
export function registerFrameBlocks(): void {
  Blockly.Blocks[FRAME_CAPTURE] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("获取").appendField(cameraField(), "SOURCE")
        .appendField("→ 画面变量");
      this.setColour("#587e9d");
      this.setPreviousStatement(true); this.setNextStatement(true);
      this.setTooltip("从所选摄像头读取画面并保存到对应变量；运行时连接该设备。");
    },
  };
  Blockly.Blocks[FRAME_VARIABLE] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("画面变量").appendField(cameraField(), "SOURCE");
      this.setColour("#587e9d"); this.setOutput(true, "CameraFrame");
      this.setTooltip("读取已获取的画面变量，包含 JPEG 图像、来源、尺寸和时间戳。");
    },
  };
  pythonGenerator.forBlock[FRAME_CAPTURE] = (block) => {
    const source = block.getFieldValue("SOURCE") as string;
    return `from xiaoxia_core.collection.frame_client import CameraFrameClient\n${frameVariableName(source)} = CameraFrameClient().read(${JSON.stringify(source)})\n`;
  };
  pythonGenerator.forBlock[FRAME_VARIABLE] = (block) => [frameVariableName(String(block.getFieldValue("SOURCE"))), Order.ATOMIC];
}

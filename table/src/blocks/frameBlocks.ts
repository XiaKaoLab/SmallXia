/** 功能：定义获取画面和画面变量积木，生成统一相机 API 的 Python 调用。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { pythonGenerator, Order } from "blockly/python";

export const FRAME_CAPTURE = "table_capture_frame";
export const FRAME_VARIABLE = "table_frame_variable";
const choices: [string, string][] = [["虚拟画面", "virtual"], ["真实画面", "real"]];
export function registerFrameBlocks(): void {
  Blockly.Blocks[FRAME_CAPTURE] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("获取").appendField(new Blockly.FieldDropdown(choices), "SOURCE")
        .appendField("→ 画面变量");
      this.setColour("#587e9d");
      this.setPreviousStatement(true); this.setNextStatement(true);
      this.setTooltip("读取最新画面并保存为 virtual_frame 或 real_frame；真实画面需先连接设备。");
    },
  };
  Blockly.Blocks[FRAME_VARIABLE] = {
    init(this: Blockly.Block) {
      this.appendDummyInput().appendField("画面变量").appendField(new Blockly.FieldDropdown(choices), "SOURCE");
      this.setColour("#587e9d"); this.setOutput(true, "CameraFrame");
      this.setTooltip("读取已获取的画面变量，包含 JPEG 图像、来源、尺寸和时间戳。");
    },
  };
  pythonGenerator.forBlock[FRAME_CAPTURE] = (block) => {
    const source = block.getFieldValue("SOURCE") as string;
    return `from xiaoxia_core.collection.frame_client import CameraFrameClient\n${source}_frame = CameraFrameClient().read(${JSON.stringify(source)})\n`;
  };
  pythonGenerator.forBlock[FRAME_VARIABLE] = (block) => [`${block.getFieldValue("SOURCE")}_frame`, Order.ATOMIC];
}

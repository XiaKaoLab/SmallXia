/** 功能：从积木实际字段生成调试及 MCP 元数据，避免新积木目录缺少字段说明。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
export class BlockMetadata {
  describe(type: string): { label: string; fields: Record<string, unknown>[] } {
    const workspace = new Blockly.Workspace();
    try {
      const block = workspace.newBlock(type);
      return { label: block.toString(80), fields: block.inputList.flatMap(input => input.fieldRow
        .filter(field => field.name).map(field => ({ name: field.name, value: field.getValue(),
          ...(field instanceof Blockly.FieldDropdown ? { options: field.getOptions(false).filter(option => typeof option[0] === 'string').map(option => option[1]) } : {}),
          ...(field instanceof Blockly.FieldNumber ? { lower: field.getMin(), upper: field.getMax() } : {}),
        }))) };
    } finally { workspace.dispose(); }
  }
}

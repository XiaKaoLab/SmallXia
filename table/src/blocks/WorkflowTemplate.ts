/** 功能：插入可编辑的示教到推理积木串，保留已有工作区并支持撤销。
 * Created on 2026-11-02; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { BLOCK_TYPE } from "./positionBlock";
import { DEMO_BEGIN, DEMO_RECORD, DEMO_FINISH, DEMO_TRAIN, DEMO_RUN, WAIT } from "./WorkflowBlocks";

export class WorkflowTemplate {
  attach(workspace: Blockly.WorkspaceSvg): void {
    workspace.registerButtonCallback("INSERT_DEMO_FLOW", () => this.insert(workspace));
  }
  private insert(workspace: Blockly.WorkspaceSvg): void {
    if (workspace.getAllBlocks(false).length > 89) return;
    Blockly.Events.setGroup(true);
    try {
      const chain = [DEMO_BEGIN, BLOCK_TYPE, WAIT, DEMO_RECORD, BLOCK_TYPE, WAIT, DEMO_RECORD, DEMO_FINISH, DEMO_TRAIN, DEMO_RUN]
        .map(type => workspace.newBlock(type));
      chain[1].setFieldValue("0", "shoulder_pan");
      chain[4].setFieldValue("0.12", "shoulder_pan");
      for (const index of [2, 5]) chain[index].setFieldValue("0.6", "SECONDS");
      for (const [index, block] of chain.entries()) {
        block.initSvg(); block.render();
        if (index) chain[index - 1].nextConnection?.connect(block.previousConnection!);
      }
      const x = Math.max(16, ...workspace.getTopBlocks(false).filter(block => block !== chain[0]).map(block => block.getRelativeToSurfaceXY().x + block.getHeightWidth().width + 24));
      chain[0].moveBy(x, 24);
      workspace.centerOnBlock(chain[0].id);
    } finally { Blockly.Events.setGroup(false); }
  }
}

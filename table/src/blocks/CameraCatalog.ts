/** 功能：缓存实际发现的相机，为 Blockly 下拉框提供设备名称和稳定标识。
 * Created on 2026-11-02; Updated on 2026-11-05
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";
import { agentClient } from "../chat/AgentClient";
import { pythonGenerator } from "blockly/python";

interface CameraDevice { id: string; name: string; source: string; physical: boolean }
export class CameraCatalog {
  private cameras: CameraDevice[] = [];
  private pending = false;
  private message = "正在查找摄像头…";
  private workspace: Blockly.WorkspaceSvg | undefined;

  options(selected?: string | null): [string, string][] {
    const options: [string, string][] = this.cameras.map(camera => [camera.name, camera.id]);
    if (selected && selected !== "unavailable" && !options.some(([, id]) => id === selected)) {
      options.push([selected === "virtual" ? "腕部虚拟相机（未就绪）" : "所选摄像头（已断开）", selected]);
    }
    return options.length ? options : [[this.message, "unavailable"]];
  }

  realOptions(selected?: string | null): [string, string][] {
    const options: [string, string][] = this.cameras.filter(camera => camera.physical).map(camera => [camera.name, camera.id]);
    if (selected && /^opencv_[0-9a-f]{16}$/.test(selected) && !options.some(([, id]) => id === selected)) options.push(["所选真实相机（离线）", selected]);
    return options.length ? options : [["未找到相机", "unavailable"]];
  }

  async refresh(): Promise<void> {
    if (this.pending || !agentClient.desktop) return;
    this.pending = true;
    try {
      const response = await agentClient.request<{ cameras: CameraDevice[] }>({ action: "list_cameras" });
      this.cameras = response.cameras;
      this.message = "未找到摄像头";
      pythonGenerator.addReservedWords(this.cameras.map(camera => frameVariableName(camera.id)).join(","));
    } catch { this.cameras = []; this.message = "查找失败，请刷新相机"; }
    finally {
      this.pending = false;
      const workspace = this.workspace;
      if (workspace && !workspace.isDragging()) {
        const blocks = [...workspace.getAllBlocks(false), ...(workspace.getFlyout()?.getWorkspace().getAllBlocks(false) ?? [])];
        for (const block of blocks) {
          if(["table_demo_run","table_policy_rollout"].includes(block.type)){
            const field=block.getField("POLICY_CAMERA") as Blockly.FieldDropdown|null;
            if(!field)continue;
            const selected=field.getValue();
            field.setOptions(()=>[["默认真实相机","real"],...this.realOptions(field.getValue()).filter(([,id])=>id.startsWith("opencv_"))]);
            field.setValue(selected);field.forceRerender();continue;
          }
          if (["table_demo_hardware", "table_demo_begin"].includes(block.type)) {
            const field = block.getField("CAMERA") as Blockly.FieldDropdown;
            const selected = field.getValue();
            field.setOptions(() => [["不录制画面", "none"], ...(block.type === 'table_demo_begin' ? [["腕部虚拟相机", "virtual"] as [string, string]] : []), ...this.realOptions(field.getValue()).filter(([, id]) => id.startsWith('opencv_'))]);
            field.setValue(selected); field.forceRerender(); continue;
          }
          if (!["table_track_red_object","table_capture_frame", "table_frame_variable", "table_calibrate_camera"].includes(block.type)) continue;
          const field = block.getField("SOURCE") as Blockly.FieldDropdown;
          const selected = String(field.getValue());
          field.setOptions(() => block.type === "table_calibrate_camera" ? this.realOptions(field.getValue()) : this.options(field.getValue()));
          if (selected !== "unavailable") field.setValue(selected);
          field.forceRerender();
        }
      }
    }
  }

  attach(workspace: Blockly.WorkspaceSvg): () => void {
    this.workspace = workspace;
    workspace.registerButtonCallback("REFRESH_CAMERAS", () => { void this.refresh(); });
    void this.refresh();
    const timer = window.setInterval(() => { void this.refresh(); }, 10000);
    return () => { clearInterval(timer); if (this.workspace === workspace) this.workspace = undefined; };
  }
}

export function frameVariableName(cameraId: string): string {
  if (cameraId === "virtual" || cameraId === "real") return `${cameraId}_frame`;
  if (/^opencv_[0-9a-f]{16}$/.test(cameraId)) return `frame_${cameraId}`;
  throw new Error("请选择相机");
}
export const cameraCatalog = new CameraCatalog();

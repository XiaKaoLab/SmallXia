/** 功能：将工具返回的关节状态、限位及通用结果显示为可读表格和字段。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import { jointNames, ToolPresentation } from "./ToolPresentation";

function ResultValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value == null || value === "") return <span>—</span>;
  if (typeof value === "boolean") return <span>{value ? "是" : "否"}</span>;
  if (typeof value !== "object") return <span>{typeof value === "string" ? ToolPresentation.value(value).slice(0, 3000) : String(value)}</span>;
  if (depth >= 4) return <span>{Array.isArray(value) ? `${value.length} 项` : `${Object.keys(value).length} 个字段`}</span>;
  const entries = Object.entries(value);
  return <dl className="tool-result-fields">{entries.slice(0, 20).map(([key, item]) => <div key={key}>
    <dt>{Array.isArray(value) ? Number(key) + 1 : ToolPresentation.label(key)}</dt>
    <dd>{key === "image_base64" ? "图像数据" : <ResultValue value={item} depth={depth + 1} />}</dd>
  </div>)}{entries.length > 20 && <div><dt>更多</dt><dd>另有 {entries.length - 20} 项</dd></div>}</dl>;
}

export function ToolResult({ name, output }: { name: string; output: string }) {
  const value = ToolPresentation.parse(output);
  const object = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
  const limits = name === "table_get_limits" && object && Object.keys(jointNames).every(key => {
    const row = object[key] as Record<string, unknown> | undefined;
    return row && typeof row.lower === "number" && typeof row.upper === "number";
  });
  const positions = object?.applied_joint_positions ?? object?.joint_positions;
  const angles = object?.unit === "rad" || name === "table_move_joints";
  return <div className="tool-result">
    {limits ? <table><thead><tr><th>关节</th><th>最小角度</th><th>最大角度</th></tr></thead><tbody>
      {Object.entries(jointNames).map(([key, label]) => {
        const row = object[key] as { lower: number; upper: number };
        return <tr key={key}><th>{label}</th><td>{(row.lower * 180 / Math.PI).toFixed(1)}°</td><td>{(row.upper * 180 / Math.PI).toFixed(1)}°</td></tr>;
      })}
    </tbody></table> : positions && typeof positions === "object" && angles ? <>
      {object?.status && <p>{ToolPresentation.value(String(object.status))}</p>}
      <table><thead><tr><th>关节</th><th>角度</th></tr></thead><tbody>
        {Object.entries(jointNames).map(([key, label]) => <tr key={key}><th>{label}</th><td>{typeof (positions as Record<string, unknown>)[key] === "number" ? `${((positions as Record<string, number>)[key] * 180 / Math.PI).toFixed(1)}°` : "—"}</td></tr>)}
      </tbody></table>
      {object?.limited === true && <p>已到运动边界</p>}
    </> : <ResultValue value={value} />}
  </div>;
}

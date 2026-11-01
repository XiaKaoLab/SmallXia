/** 功能：统一线性图标按钮的可访问名称与交互样式。
 * Created on 2026-11-01; Updated on 2026-11-01
 * @author: https://github.com/Linmoqian
 */
import type { ButtonHTMLAttributes } from "react";

export function IconButton({ label, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button type="button" title={label} aria-label={label} className={`icon-button ${className}`} {...props} />;
}

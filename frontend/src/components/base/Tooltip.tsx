import {
  useCallback,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

/**
 * TooltipBubble — 全站统一提示气泡的「外观唯一真源」。
 *
 * 深色气泡、圆角、字号、内边距都在这里定义。既供 Portal 版 Tooltip 使用，
 * 也供 recharts 等第三方图表库的自定义 tooltip 内容复用（其扇区/柱条是 SVG，
 * 无法直接套 Portal tooltip，但可以通过本组件保持外观一致）。
 */
export interface TooltipBubbleProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export function TooltipBubble({
  children,
  className = "",
  style,
}: TooltipBubbleProps) {
  return (
    <div
      role="tooltip"
      style={style}
      className={`pointer-events-none z-[130] max-w-[260px] whitespace-nowrap rounded-md border border-foreground-700 bg-foreground-950 px-2.5 py-1 text-[11px] font-medium leading-snug text-background-50 ${className}`.trim()}
    >
      {children}
    </div>
  );
}

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  disabled?: boolean;
  /** 透传到挂载壳的类名，便于把壳当作 flex 子项参与布局。 */
  className?: string;
  /** 透传到挂载壳的内联样式，便于按占比设置宽度等。 */
  style?: CSSProperties;
}

type Placement = "top" | "bottom";

interface TooltipPosition {
  top: number;
  left: number;
  placement: Placement;
}

/**
 * Tooltip — 全站统一的悬浮提示。
 *
 * 通过 Portal 挂载到 document.body，用 fixed 定位，因此不会被父级容器的
 * overflow-hidden 裁切，也不受 z-index 层级影响。
 * 空间不足时（元素贴近视口顶部）自动翻转到元素下方，避免贴边被挤出屏幕。
 * 外观统一走 TooltipBubble。
 */
export default function Tooltip({
  content,
  children,
  disabled = false,
  className,
  style,
}: TooltipProps) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [position, setPosition] = useState<TooltipPosition | null>(null);

  const show = useCallback(() => {
    if (disabled) return;
    const node = anchorRef.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    const placement: Placement = rect.top < 56 ? "bottom" : "top";
    setPosition({
      top: placement === "top" ? rect.top - 8 : rect.bottom + 8,
      left: rect.left + rect.width / 2,
      placement,
    });
  }, [disabled]);

  const hide = useCallback(() => setPosition(null), []);

  return (
    <span
      ref={anchorRef}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      className={`inline-flex ${className ?? ""}`.trim()}
      style={style}
    >
      {children}
      {position &&
        createPortal(
          <TooltipBubble
            className="animate-fade-in"
            style={{
              position: "fixed",
              top: position.top,
              left: position.left,
              transform:
                position.placement === "top"
                  ? "translate(-50%, -100%)"
                  : "translate(-50%, 0)",
            }}
          >
            {content}
          </TooltipBubble>,
          document.body,
        )}
    </span>
  );
}
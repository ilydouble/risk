import Tooltip from "@/components/base/Tooltip";
import { RISK_HINT } from "@/constants/status";
import type { RiskLevel } from "@/types";
import { useTranslation } from "react-i18next";

/**
 * StatusDot — 全站状态小圆点的唯一真源。
 *
 * 统一规范（蓝 · 赭金 · 红）：
 *   low    → 钴蓝  —— 低风险 / 正常 / 已连接 / 已上线 / 存续
 *   medium → 赭金  —— 中风险 / 降级 / 演示模式 / 需关注
 *   high   → 红    —— 高风险 / 中断 / 告警
 *
 * 连接状态、系统服务、风险等级一律复用本组件与 risk-bg-* 语义色，
 * 禁止在业务组件里各自写色值映射，避免色相漂移。
 *
 * tooltip：默认关闭（纯圆点多为装饰或已带文字标签）；置 true 时悬浮显示颜色语义。
 */
const LEVEL_CLASS: Record<RiskLevel, string> = {
  low: "risk-bg-low",
  medium: "risk-bg-medium",
  high: "risk-bg-high",
};

const SIZE_CLASS = {
  xs: "h-1.5 w-1.5",
  sm: "h-2 w-2",
  md: "h-2.5 w-2.5",
} as const;

export type StatusDotSize = keyof typeof SIZE_CLASS;

export interface StatusDotProps {
  level: RiskLevel;
  size?: StatusDotSize;
  pulse?: boolean;
  /** 是否显示颜色语义 tooltip（默认 false）。 */
  tooltip?: boolean;
  className?: string;
}

export default function StatusDot({
  level,
  size = "sm",
  pulse = false,
  tooltip = false,
  className = "",
}: StatusDotProps) {
  const { t } = useTranslation();
  const dot = (
    <span
      aria-hidden="true"
      className={`inline-block shrink-0 rounded-full ${SIZE_CLASS[size]} ${LEVEL_CLASS[level]} ${
        pulse ? "animate-pulse-soft" : ""
      } ${className}`.trim()}
    />
  );

  if (!tooltip) return dot;

  return <Tooltip content={t(RISK_HINT[level])}>{dot}</Tooltip>;
}
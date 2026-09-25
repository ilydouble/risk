import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import StatusDot, { type StatusDotSize } from "@/components/base/StatusDot";
import Tooltip from "@/components/base/Tooltip";
import { RISK_HINT } from "@/constants/status";
import type { RiskLevel } from "@/types";

/**
 * StatusPill — 全站「状态点 + 状态文字」标签的唯一真源。
 *
 * 适用场景（标签样式统一由本组件负责，业务组件禁止各写各的）：
 *   · 连接状态（侧栏底部）
 *   · 系统服务（总览看板）
 *   · 主体存续 / 模型上线等运行状态
 *   · 风险等级徽章（RiskBadge 基于它封装）
 *
 * 语义色沿用「蓝 · 赭金 · 红」，色值来自 CSS 变量 --risk-*，保证色相永远一致：
 *   low    → 钴蓝  —— 低风险 / 正常 / 已连接 / 已上线 / 存续
 *   medium → 赭金  —— 中风险 / 降级 / 演示模式 / 需关注
 *   high   → 红    —— 高风险 / 中断 / 告警
 *
 * 统一 tooltip：默认悬浮显示该等级的颜色语义（文案取自 RISK_HINT），
 * 传字符串可覆盖文案（如动作说明），传 false 可关闭。
 */
const TEXT_CLASS: Record<RiskLevel, string> = {
  low: "risk-text-low",
  medium: "risk-text-medium",
  high: "risk-text-high",
};

const SOFT_CLASS: Record<RiskLevel, string> = {
  low: "risk-soft-low",
  medium: "risk-soft-medium",
  high: "risk-soft-high",
};

const BORDER_CLASS: Record<RiskLevel, string> = {
  low: "risk-border-low",
  medium: "risk-border-medium",
  high: "risk-border-high",
};

const SIZE_CLASS = {
  sm: "gap-1.5 px-2 py-0.5 text-[11px]",
  md: "gap-1.5 px-2.5 py-1 text-xs",
} as const;

export type StatusPillSize = keyof typeof SIZE_CLASS;

export interface StatusPillProps {
  level: RiskLevel;
  label: ReactNode;
  size?: StatusPillSize;
  dotSize?: StatusDotSize;
  pulse?: boolean;
  variant?: "soft" | "plain";
  /** 默认 true=显示颜色语义提示；可传字符串覆盖文案；传 false 关闭。 */
  tooltip?: boolean | string;
  className?: string;
}

export default function StatusPill({
  level,
  label,
  size = "md",
  dotSize = "xs",
  pulse = false,
  variant = "soft",
  tooltip = true,
  className = "",
}: StatusPillProps) {
  const { t } = useTranslation();
  const variantClass =
    variant === "soft"
      ? `border ${SOFT_CLASS[level]} ${BORDER_CLASS[level]}`
      : "border border-transparent";

  const pill = (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full font-medium ${SIZE_CLASS[size]} ${variantClass} ${TEXT_CLASS[level]} ${className}`.trim()}
    >
      <StatusDot level={level} size={dotSize} pulse={pulse} />
      {label}
    </span>
  );

  if (tooltip === false) return pill;

  return (
    <Tooltip content={typeof tooltip === "string" ? tooltip : t(RISK_HINT[level])}>
      {pill}
    </Tooltip>
  );
}
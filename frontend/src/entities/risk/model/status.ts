import type { RiskLevel } from "@/shared/model/risk";

/**
 * 状态语义提示 —— 全站状态标签 tooltip 的唯一文案真源。
 *
 * 与 CSS 变量 --risk-low / --risk-medium / --risk-high 三色语义严格一一对应，
 * 所有 tooltip 文案都从这里取，禁止在业务组件里另写一套，保证「蓝 · 赭金 · 红」口径一致。
 *   low    → 钴蓝  —— 低风险 / 正常 / 已连接 / 已上线 / 存续
 *   medium → 赭金  —— 中风险 / 降级 / 演示模式 / 需关注
 *   high   → 朱红  —— 高风险 / 中断 / 告警
 */
export const RISK_HINT: Record<RiskLevel, string> = {
  low: "risk.hintLow",
  medium: "risk.hintMedium",
  high: "risk.hintHigh",
};

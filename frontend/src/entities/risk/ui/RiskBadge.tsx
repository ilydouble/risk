import { useTranslation } from "react-i18next";
import StatusPill from "@/entities/risk/ui/StatusPill";
import type { RiskLevel } from "@/shared/model/risk";

interface RiskBadgeProps {
  level: RiskLevel;
  label?: string;
  size?: "sm" | "md";
}

export default function RiskBadge({ level, label, size = "md" }: RiskBadgeProps) {
  const { t } = useTranslation();
  return (
    <StatusPill
      level={level}
      label={label ?? t(`risk.${level}`)}
      size={size}
      dotSize="xs"
    />
  );
}

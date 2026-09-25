import { useTranslation } from "react-i18next";
import StatusPill from "@/components/base/StatusPill";
import { systemServices } from "@/mocks/overview";
import type { RiskLevel, ServiceStatus } from "@/types";

const STATUS_MAP: Record<ServiceStatus, { labelKey: string; level: RiskLevel }> = {
  operational: { labelKey: "status.operational", level: "low" },
  degraded: { labelKey: "status.degraded", level: "medium" },
  down: { labelKey: "status.down", level: "high" },
};

// 与 mocks/overview.ts 的 systemServices 顺序一致，用于取本地化文案。
const SERVICE_KEYS = ["scoring", "graph", "credit", "report"];

export default function SystemStatusPanel() {
  const { t } = useTranslation();

  return (
    <ul className="divide-y divide-background-200/70">
      {systemServices.map((service, index) => {
        const status = STATUS_MAP[service.status];
        const key = SERVICE_KEYS[index] ?? "scoring";
        return (
          <li
            key={service.name}
            className="flex flex-col gap-2 px-4 py-3.5 transition-colors hover:bg-background-200/40 sm:flex-row sm:items-center sm:gap-4"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate text-[13px] font-medium text-foreground-900">
                  {t(`overview.services.${key}.name`)}
                </p>
                <StatusPill
                  level={status.level}
                  label={t(status.labelKey)}
                  size="sm"
                  pulse={service.status !== "operational"}
                />
              </div>
              <p className="mt-0.5 truncate text-[11px] text-foreground-500">
                {t(`overview.services.${key}.desc`)}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <p className="font-mono text-[12px] text-foreground-800">
                {service.latency}
              </p>
              <p className="font-mono text-[10px] text-foreground-500">
                {service.uptime}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
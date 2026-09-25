import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import {
  modelBoundaries,
  modelCompliance,
  modelLimitations,
  modelMonitoring,
} from "@/mocks/modelCard";
import { useLang } from "@/hooks/useLang";
import type { ModelGovernanceItem } from "@/types";

interface Section {
  key: string;
  title: string;
  subtitle: string;
  icon: string;
  items: ModelGovernanceItem[];
}

export default function GovernanceCard() {
  const { t } = useTranslation();
  const { pick } = useLang();

  const sections: Section[] = [
    {
      key: "limitations",
      title: t("model.governance.limitations"),
      subtitle: t("model.governance.limitationsSub"),
      icon: "ri-error-warning-line",
      items: modelLimitations,
    },
    {
      key: "boundaries",
      title: t("model.governance.boundaries"),
      subtitle: t("model.governance.boundariesSub"),
      icon: "ri-roadster-line",
      items: modelBoundaries,
    },
    {
      key: "compliance",
      title: t("model.governance.compliance"),
      subtitle: t("model.governance.complianceSub"),
      icon: "ri-shield-keyhole-line",
      items: modelCompliance,
    },
    {
      key: "monitoring",
      title: t("model.governance.monitoring"),
      subtitle: t("model.governance.monitoringSub"),
      icon: "ri-radar-line",
      items: modelMonitoring,
    },
  ];

  return (
    <Card
      title={t("model.governance.title")}
      subtitle={t("model.governance.subtitle")}
      icon="ri-scales-3-line"
      bodyClassName="p-4"
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {sections.map((section) => (
          <div
            key={section.key}
            className="rounded-md border border-background-200 bg-background-50 p-3.5"
          >
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-md bg-secondary-500/12 text-secondary-300">
                <i className={`${section.icon} text-[15px]`}></i>
              </span>
              <div>
                <p className="text-[13px] font-semibold text-foreground-950">
                  {section.title}
                </p>
                <p className="text-[10px] text-foreground-500">{section.subtitle}</p>
              </div>
            </div>

            <ul className="mt-3 space-y-2.5">
              {section.items.map((item) => (
                <li key={item.id} className="flex items-start gap-2">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-background-200/70 text-foreground-600">
                    <i className={`${item.icon} text-[13px]`}></i>
                  </span>
                  <div className="min-w-0">
                    <p className="text-[12px] font-medium text-foreground-800">
                      {pick(item.title, item.titleEn)}
                    </p>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-foreground-500">
                      {pick(item.desc, item.descEn)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
}
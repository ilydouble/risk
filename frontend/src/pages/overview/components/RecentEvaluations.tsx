import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { companies } from "@/features/demo-scenarios/model/fixtures/companies";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import { useLang } from "@/shared/lib/useLang";

const recent = companies.slice(0, 6);

export default function RecentEvaluations() {
  const { t } = useTranslation();
  const { pick } = useLang();
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left">
        <thead>
          <tr className="border-b border-background-200/70">
            <th className="px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-foreground-500">
              {t("overview.recent.colCompany")}
            </th>
            <th className="px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-foreground-500">
              {t("overview.recent.colScore")}
            </th>
            <th className="px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-foreground-500">
              {t("overview.recent.colPd")}
            </th>
            <th className="px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-foreground-500">
              {t("overview.recent.colRisk")}
            </th>
            <th className="px-4 py-2.5 text-right text-[11px] font-medium uppercase tracking-wider text-foreground-500">
              {t("overview.recent.colAction")}
            </th>
          </tr>
        </thead>
        <tbody>
          {recent.map((c) => (
            <tr
              key={c.id}
              className="border-b border-background-200/50 transition-colors last:border-b-0 hover:bg-background-200/40"
            >
              <td className="px-4 py-3">
                <Link
                  to={`/company/${c.id}`}
                  className="flex items-center gap-2.5 cursor-pointer"
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-background-200 text-foreground-600">
                    <i className="ri-building-2-line text-[15px]"></i>
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-medium text-foreground-900 hover:text-primary-400">
                      {pick(c.nameCn, c.nameEn)}
                    </span>
                    <span className="block truncate font-mono text-[10px] text-foreground-500">
                      {c.country} · {c.industry}
                    </span>
                  </span>
                </Link>
              </td>
              <td className="px-4 py-3">
                <span className="font-mono text-sm font-semibold text-foreground-950">
                  {c.creditScore}
                </span>
              </td>
              <td className="px-4 py-3 font-mono text-[13px] text-foreground-700">
                {c.defaultProb.toFixed(1)}%
              </td>
              <td className="px-4 py-3">
                <RiskBadge level={c.riskLevel} size="sm" />
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  to={`/score/${c.id}`}
                  className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-background-300 px-2.5 py-1.5 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400 cursor-pointer"
                >
                  <i className="ri-line-chart-line text-[13px]"></i>
                  {t("overview.recent.viewScore")}
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
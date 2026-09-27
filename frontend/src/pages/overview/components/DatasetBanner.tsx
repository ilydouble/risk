import { useTranslation } from "react-i18next";
import type { components } from "@/shared/api/generated/schema";

type OverviewDatasetDTO = components["schemas"]["OverviewDatasetDTO"];

export default function DatasetBanner({ dataset }: { dataset: OverviewDatasetDTO }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border border-primary-500/25 bg-primary-500/8 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-primary-500/15 px-2.5 py-1 text-[11px] font-semibold text-primary-400">
              {t("overview.source.real")}
            </span>
            <span className="font-mono text-[11px] text-foreground-500">{dataset.country}</span>
          </div>
          <h2 className="mt-2 font-heading text-base font-semibold text-foreground-950">{dataset.name}</h2>
          <p className="mt-1 text-xs leading-relaxed text-foreground-600">{t("overview.source.scope")}</p>
        </div>
        <dl className="grid shrink-0 grid-cols-2 gap-x-6 gap-y-1 text-xs">
          <dt className="text-foreground-500">{t("overview.source.generated")}</dt>
          <dd className="text-right font-mono text-foreground-800">{dataset.generatedAt.slice(0, 10)}</dd>
          <dt className="text-foreground-500">SHA-256</dt>
          <dd className="text-right font-mono text-foreground-800" title={dataset.sourceArchiveSha256}>{dataset.sourceArchiveSha256.slice(0, 12)}</dd>
        </dl>
      </div>
    </div>
  );
}

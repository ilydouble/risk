import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

interface Resource {
  to: string;
  labelKey: string;
  descKey: string;
  icon: string;
}

const RESOURCES: Resource[] = [
  {
    to: "/model",
    labelKey: "model.resources.dashboard.label",
    descKey: "model.resources.dashboard.desc",
    icon: "ri-line-chart-line",
  },
  {
    to: "/batch",
    labelKey: "model.resources.batch.label",
    descKey: "model.resources.batch.desc",
    icon: "ri-stack-line",
  },
  {
    to: "/search",
    labelKey: "model.resources.search.label",
    descKey: "model.resources.search.desc",
    icon: "ri-search-line",
  },
  {
    to: "/",
    labelKey: "model.resources.overview.label",
    descKey: "model.resources.overview.desc",
    icon: "ri-dashboard-3-line",
  },
];

export default function ModelResourceLinks() {
  const { t } = useTranslation();
  return (
    <section className="animate-fade-up grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {RESOURCES.map((resource) => (
        <Link
          key={resource.to}
          to={resource.to}
          className="group flex cursor-pointer items-start gap-3 rounded-lg border border-background-200 bg-background-100 p-4 transition-colors hover:border-primary-400"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
            <i className={`${resource.icon} text-[17px]`}></i>
          </span>
          <div className="min-w-0">
            <p className="flex items-center gap-1 text-[13px] font-medium text-foreground-950">
              {t(resource.labelKey)}
              <i className="ri-arrow-right-up-line text-[13px] text-foreground-400 transition-colors group-hover:text-primary-400"></i>
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-foreground-500">
              {t(resource.descKey)}
            </p>
          </div>
        </Link>
      ))}
    </section>
  );
}
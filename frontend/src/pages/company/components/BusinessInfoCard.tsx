import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import { useLang } from "@/hooks/useLang";
import type { Company, CompanyFactsEn, CompanyFacts } from "@/types";

interface BusinessInfoCardProps {
  company: Company;
  facts: CompanyFacts;
  factsEn?: CompanyFactsEn;
}

export default function BusinessInfoCard({
  company,
  facts,
  factsEn,
}: BusinessInfoCardProps) {
  const { t } = useTranslation();
  const { pick } = useLang();

  const fields = [
    {
      label: t("company.facts.regNo"),
      value: company.regNo,
      icon: "ri-hashtag",
      mono: true,
    },
    {
      label: t("company.facts.nameCn"),
      value: company.nameCn,
      icon: "ri-building-2-line",
      mono: false,
    },
    {
      label: t("company.facts.nameEn"),
      value: company.nameEn,
      icon: "ri-translate-2",
      mono: false,
    },
    {
      label: t("company.facts.country"),
      value: pick(company.country, company.countryEn),
      icon: "ri-earth-line",
      mono: false,
    },
    {
      label: t("company.facts.industry"),
      value: pick(company.industry, company.industryEn),
      icon: "ri-stack-line",
      mono: false,
    },
    {
      label: t("company.facts.established"),
      value: facts.established,
      icon: "ri-calendar-line",
      mono: true,
    },
    {
      label: t("company.facts.registeredCapital"),
      value: pick(facts.registeredCapital, factsEn?.registeredCapital),
      icon: "ri-money-cny-circle-line",
      mono: false,
    },
    {
      label: t("company.facts.paidInCapital"),
      value: pick(facts.paidInCapital, factsEn?.paidInCapital),
      icon: "ri-wallet-3-line",
      mono: false,
    },
    {
      label: t("company.facts.legalPerson"),
      value: pick(facts.legalPerson, factsEn?.legalPerson),
      icon: "ri-user-star-line",
      mono: false,
    },
    {
      label: t("company.facts.actualController"),
      value: pick(facts.actualController, factsEn?.actualController),
      icon: "ri-user-follow-line",
      mono: false,
    },
    {
      label: t("company.facts.controllerStake"),
      value: pick(facts.controllerStake, factsEn?.controllerStake),
      icon: "ri-pie-chart-line",
      mono: false,
    },
    {
      label: t("company.facts.employees"),
      value: pick(facts.employees, factsEn?.employees),
      icon: "ri-group-line",
      mono: false,
    },
    {
      label: t("company.facts.listed"),
      value: pick(facts.listed, factsEn?.listed),
      icon: "ri-stock-line",
      mono: false,
    },
    {
      label: t("company.facts.ratingAgency"),
      value: pick(facts.ratingAgency, factsEn?.ratingAgency),
      icon: "ri-award-line",
      mono: false,
    },
    {
      label: t("company.facts.mainBanks"),
      value: pick(facts.mainBanks, factsEn?.mainBanks),
      icon: "ri-bank-line",
      mono: false,
    },
    {
      label: t("company.facts.settlement"),
      value: pick(facts.settlement, factsEn?.settlement),
      icon: "ri-exchange-dollar-line",
      mono: false,
    },
    {
      label: t("company.facts.revenue"),
      value: pick(facts.revenue, factsEn?.revenue),
      icon: "ri-line-chart-line",
      mono: false,
    },
    {
      label: t("company.facts.netMargin"),
      value: pick(facts.netMargin, factsEn?.netMargin),
      icon: "ri-percent-line",
      mono: false,
    },
  ];

  return (
    <Card
      title={t("company.facts.title")}
      subtitle={t("company.facts.subtitle")}
      icon="ri-file-list-3-line"
      bodyClassName="p-4"
      action={
        <span className="flex items-center gap-1.5 whitespace-nowrap rounded-full border border-primary-400/40 bg-primary-500/10 px-2.5 py-1 text-[11px] text-primary-400">
          <i className="ri-shield-check-line text-[13px]"></i>
          {t("company.facts.verified")}
        </span>
      }
    >
      <dl className="grid grid-cols-1 gap-x-5 gap-y-0 sm:grid-cols-2 xl:grid-cols-3">
        {fields.map((field) => (
          <div
            key={field.label}
            className="flex items-start gap-2.5 border-b border-background-200/60 py-2.5"
          >
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-background-200 text-foreground-500">
              <i className={`${field.icon} text-[13px]`}></i>
            </span>
            <div className="min-w-0">
              <dt className="text-[11px] text-foreground-500">{field.label}</dt>
              <dd
                className={`mt-0.5 break-words text-[13px] leading-snug text-foreground-900 ${
                  field.mono ? "font-mono" : ""
                }`}
              >
                {field.value}
              </dd>
            </div>
          </div>
        ))}
      </dl>
    </Card>
  );
}
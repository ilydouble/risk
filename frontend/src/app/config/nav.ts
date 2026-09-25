import { DEFAULT_COMPANY_ID } from "@/entities/company/model/defaults";

export interface NavItem {
  key: string;
  /** i18n key，渲染时用 t() 取本地化文案。 */
  labelKey: string;
  path: string;
  icon: string;
}

export interface NavGroup {
  key: string;
  /** i18n key，渲染时用 t() 取本地化文案。 */
  labelKey: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    key: "workspace",
    labelKey: "nav.workspace",
    items: [
      {
        key: "overview",
        labelKey: "nav.overview",
        path: "/",
        icon: "ri-dashboard-3-line",
      },
      {
        key: "search",
        labelKey: "nav.search",
        path: "/search",
        icon: "ri-search-line",
      },
      {
        key: "company",
        labelKey: "nav.company",
        path: `/company/${DEFAULT_COMPANY_ID}`,
        icon: "ri-building-2-line",
      },
    ],
  },
  {
    key: "modeling",
    labelKey: "nav.modeling",
    items: [
      {
        key: "model",
        labelKey: "nav.model",
        path: "/model-card",
        icon: "ri-file-info-line",
      },
      {
        key: "batch",
        labelKey: "nav.batch",
        path: "/batch",
        icon: "ri-stack-line",
      },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

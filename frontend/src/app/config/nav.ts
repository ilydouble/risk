import { WORKBENCH_SECTIONS, workbenchPath } from "@/features/modeling/model/workbenchSections";

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
      { key: "chat", labelKey: "nav.chat", path: "/chat", icon: "ri-chat-3-line" },
    ],
  },
  {
    key: "modeling",
    labelKey: "nav.modelingWorkbench",
    items: WORKBENCH_SECTIONS.map(({ id, icon }) => ({
      key: `modeling-${id}`,
      labelKey: `modeling.sections.${id}`,
      path: workbenchPath(id),
      icon,
    })),
  },
  {
    key: "settings",
    labelKey: "nav.settings",
    items: [
      { key: "settings", labelKey: "nav.aiSettings", path: "/settings/ai-model", icon: "ri-settings-3-line" },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

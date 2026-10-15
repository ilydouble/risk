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
      { key: "data-prep", labelKey: "nav.dataPrep", path: "/data-prep", icon: "ri-file-search-line" },
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
    labelKey: "nav.modeling",
    items: [
      {
        key: "modeling",
        labelKey: "nav.modelingWorkbench",
        path: "/modeling",
        icon: "ri-function-line",
      },
      {
        key: "model",
        labelKey: "nav.model",
        path: "/modeling?tab=model",
        icon: "ri-file-info-line",
      },
    ],
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

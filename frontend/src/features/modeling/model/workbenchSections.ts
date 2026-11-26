export const WORKBENCH_SECTIONS = [
  { id: "datasets", icon: "ri-database-2-line" },
  { id: "import", icon: "ri-upload-2-line" },
  { id: "enterprise-data", icon: "ri-building-2-line" },
  { id: "new-experiment", icon: "ri-flask-line" },
  { id: "experiments", icon: "ri-list-check-2" },
  { id: "models", icon: "ri-file-info-line" },
] as const;

export type WorkbenchSection = (typeof WORKBENCH_SECTIONS)[number]["id"];

export function workbenchPath(section: WorkbenchSection) {
  return `/modeling/${section}`;
}

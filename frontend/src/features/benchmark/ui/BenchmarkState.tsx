import { useTranslation } from "react-i18next";

export default function BenchmarkState({ loading, error, retry }: { loading: boolean; error: string; retry: () => void }) {
  const { t } = useTranslation();
  if (loading) return <div role="status" className="rounded-lg border border-background-200 bg-background-100 p-8 text-sm text-foreground-500">{t("benchmark.loading")}</div>;
  if (error) return <div role="alert" className="rounded-lg border border-accent-500/30 bg-background-100 p-8 text-sm text-foreground-700">{error}<button type="button" onClick={retry} className="ml-4 rounded-md bg-primary-500 px-3 py-1.5 text-background-50">{t("benchmark.retry")}</button></div>;
  return null;
}

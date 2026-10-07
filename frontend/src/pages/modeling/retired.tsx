import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
export default function RetiredBenchmark() {
  const { t } = useTranslation();
  return (
    <section className="m-8 rounded-xl border border-background-200 bg-background-100 p-8">
      <h1 className="text-xl font-semibold">{t("modeling.retired")}</h1>
      <p className="my-4 text-foreground-500">{t("modeling.retiredNote")}</p>
      <Link to="/modeling" className="text-primary-500 underline">
        {t("modeling.title")}
      </Link>
    </section>
  );
}

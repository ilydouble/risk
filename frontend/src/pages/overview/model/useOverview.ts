import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { requestGetOverview } from "@/entities/overview/api/overviewApi";
import type { ResponseGetOverview } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";

export function useOverview() {
  const { t } = useTranslation();
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<ResponseGetOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    requestGetOverview({})
      .then((response) => {
        if (active) setData(response);
      })
      .catch((failure) => {
        if (active) {
          setError(handleApiError(failure, {
            OVERVIEW_DATA_UNAVAILABLE: t("overview.unavailable"),
          }));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [revision, t]);

  return {
    data,
    loading,
    error,
    retry: () => setRevision((value) => value + 1),
  };
}

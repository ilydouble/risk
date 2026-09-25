import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import * as BenchmarkApi from "@/entities/benchmark/api/benchmarkApi";
import { useBenchmark } from "@/features/benchmark/model/useBenchmark";
import BenchmarkShell from "@/features/benchmark/ui/BenchmarkShell";
import BenchmarkState from "@/features/benchmark/ui/BenchmarkState";
import Card from "@/shared/ui/Card";

export default function BenchmarkSearch() {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const { data, loading, error, retry } = useBenchmark(`${keyword}:${page}`, () => BenchmarkApi.requestSearchBenchmark({ keyword, pagination: { page, pageSize: 20 } }));
  const submit = (event: FormEvent) => { event.preventDefault(); setPage(1); setKeyword(input.trim()); };
  return <BenchmarkShell title={t("benchmark.search")}>
    <Card title={t("benchmark.search")} icon="ri-search-line" bodyClassName="p-4">
      <form onSubmit={submit} className="flex flex-wrap gap-2"><input aria-label={t("benchmark.searchInput")} value={input} onChange={(event) => setInput(event.target.value)} placeholder={t("benchmark.searchInput")} className="min-w-56 flex-1 rounded-md border border-background-300 bg-background-50 px-3 py-2 text-sm text-foreground-900 outline-none focus:border-primary-500" /><button type="submit" className="rounded-md bg-primary-500 px-4 py-2 text-sm text-background-50">{t("benchmark.search")}</button></form>
    </Card>
    <BenchmarkState loading={loading} error={error} retry={retry} />
    {data && !error && <Card title={t("benchmark.results", { count: data.total })} bodyClassName="divide-y divide-background-200">
      {data.items.length === 0 && <p className="p-6 text-sm text-foreground-500">{t("benchmark.empty")}</p>}
      {data.items.map((item) => <Link key={item.id} to={`/benchmark/company/${item.id}`} className="flex flex-wrap items-center gap-3 px-4 py-3 transition-colors hover:bg-background-200/40"><span className="font-mono text-sm font-semibold text-primary-400">{item.id}</span><span className="text-xs text-foreground-500">{item.community}</span><span className="ml-auto font-mono text-xs text-foreground-800">{(item.riskProbability * 100).toFixed(1)}%</span><i className="ri-arrow-right-s-line text-foreground-500" /></Link>)}
      <div className="flex items-center justify-between px-4 py-3 text-xs text-foreground-600"><button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="disabled:opacity-40">{t("benchmark.previous")}</button><span>{page} / {Math.max(1, Math.ceil(data.total / 20))}</span><button type="button" disabled={page * 20 >= data.total} onClick={() => setPage(page + 1)} className="disabled:opacity-40">{t("benchmark.next")}</button></div>
    </Card>}
  </BenchmarkShell>;
}

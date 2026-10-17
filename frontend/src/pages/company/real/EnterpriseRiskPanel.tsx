import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { requestEnterpriseOverview, requestPredictModel } from "@/entities/modeling/api/modelingApi";
import type { ResponseEnterpriseCompany, ResponseEnterpriseOverview } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import Card from "@/shared/ui/Card";

const featureNames: Record<string, string> = {
  age_months: "企业年龄（月）", n_charges: "抵押登记数量", n_charges_outstanding: "未解除抵押数量",
  addr_company_count: "同地址企业数", n_net_dir: "董事网络数量", max_span: "最大跨度", sum_span: "累计跨度",
};
const number = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 4 });

export function EnterpriseRiskPanel({ data, modelId, onUpdated }: {
  data: ResponseEnterpriseCompany; modelId: string; onUpdated: () => void;
}) {
  const datasetId = data.dataset.id;
  const companyId = data.company.nodeId ?? "";
  const [models, setModels] = useState<ResponseEnterpriseOverview["models"]>([]);
  const [selected, setSelected] = useState(modelId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    requestEnterpriseOverview({ datasetId }).then(result => {
      if (active) { setModels(result.models); setSelected(modelId || (result.models.length === 1 ? result.models[0].id : "")); }
    }).catch(cause => { if (active) setError(handleApiError(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [datasetId, modelId]);
  async function predict(identity: string) {
    setBusy(true); setError("");
    try { await requestPredictModel({ modelId: identity, companyIds: [companyId], explain: true }); onUpdated(); }
    catch (cause) { setError(handleApiError(cause, {
      MODEL_RESOURCE_NOT_FOUND: "企业不在此模型绑定图内，或模型不存在。请检查企业与模型范围。",
      RISKGNN_COMPANY_NOT_FOUND: "该企业不在此模型绑定图内，当前暂不支持新企业推理。",
      MODEL_EXPLANATION_UNAVAILABLE: "该模型暂不支持解释，请使用已发布的 RiskGNN+ 模型。",
    })); }
    finally { setBusy(false); }
  }
  const assistantLink = (identity: string) => `/chat?${new URLSearchParams({ riskDataset: datasetId, riskModel: identity, riskCompany: companyId })}`;
  return <Card title="企业状态预测与解释" subtitle="模型分数未经校准；请结合模型测试质量、标签含义和来源证据判断。" icon="ri-cpu-line" bodyClassName="space-y-4 p-5">
    {error && <p role="alert" className="text-sm text-danger-500">{error}</p>}
    {loading ? <p role="status" className="text-sm text-foreground-500">正在加载可用模型…</p> : models.length > 0 ? <div className="flex flex-wrap items-end gap-3">
      <label className="text-xs">本数据集的已发布模型<select value={selected} onChange={event => setSelected(event.target.value)} disabled={busy} className="mt-2 block max-w-full rounded-md border border-background-300 bg-background-50 p-2 text-sm"><option value="">请选择模型版本</option>{models.map(model => <option key={model.id} value={model.id}>{model.name} · {model.id.slice(0, 8)}</option>)}</select></label>
      <button type="button" disabled={busy || !selected} onClick={() => void predict(selected)} className="rounded-md bg-primary-500 px-4 py-2 text-xs text-white disabled:opacity-50">{busy ? "正在预测并计算解释…" : "预测并解释"}</button>
      {selected && <Link to={assistantLink(selected)} className="py-2 text-xs text-primary-400">让智能助手解读 →</Link>}
    </div> : !error && <p className="text-sm text-foreground-500">本数据集暂无已发布模型，请先完成训练和测试，再在工作台发布模型版本。</p>}
    <Link to={`/modeling?dataset=${encodeURIComponent(datasetId)}&tab=model`} className="inline-block text-xs text-primary-400">打开工作台模型管理 →</Link>
    {data.predictions.length === 0 && <p className="text-sm text-foreground-500">该企业尚无已保存的预测结果。</p>}
    {data.predictions.map(prediction => {
      const explanation = prediction.result.explanation;
      return <section key={prediction.modelId} className="space-y-3 rounded-md border border-background-200 p-4">
        <h3 className="text-sm font-medium">{prediction.modelName}</h3>
        <p className="break-all font-mono text-[10px] text-foreground-500">模型版本：{prediction.modelId}</p>
        <p className="text-lg font-semibold">状态分类分数 {(prediction.result.probability * 100).toFixed(2)}% <span className="text-sm font-normal">· 预测类别 {prediction.result.predictedLabel}</span></p>
        <p className="text-xs text-foreground-500">融合分数：{prediction.result.fusedProbability == null ? "—" : `${(prediction.result.fusedProbability * 100).toFixed(2)}%`} · 证据不确定性：{prediction.result.uncertainty == null ? "—" : number(prediction.result.uncertainty)} · 分支冲突度：{prediction.result.conflict == null ? "—" : number(prediction.result.conflict)}</p>
        {explanation ? <>
          <p className="break-words text-xs leading-6 text-foreground-500">标签定义：{explanation.target}</p>
          <p className="text-xs text-foreground-500">评估时间：{new Date(explanation.evaluatedAt).toLocaleString()} · 测试 ROC-AUC：{typeof explanation.testMetrics.rocAuc === "number" ? explanation.testMetrics.rocAuc.toFixed(4) : "未提供"}</p>
          <div className="rounded-md border border-warning-500/30 bg-warning-500/5 p-3 text-xs leading-6">{explanation.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>
          <h4 className="text-sm font-medium">特征敏感性</h4>
          <p className="text-xs leading-6 text-foreground-500">逐项替换为训练目标企业中位数（{explanation.referenceCount.toLocaleString()} 家），固定其余输入与关系图。变化为原分数减去替换后分数，单位为百分点；不是 SHAP，各项不能相加。</p>
          <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-foreground-500"><tr>{["特征", "模型输入值", "训练参考值", "相对参考值的影响"].map(label => <th key={label} className="whitespace-nowrap p-2 font-medium">{label}</th>)}</tr></thead><tbody>{explanation.features.map(feature => <tr key={feature.feature} className="border-t border-background-200"><td className="p-2">{featureNames[feature.feature] ?? feature.feature}<span className="block font-mono text-[10px] text-foreground-500">{feature.feature}</span></td><td className="p-2">{number(feature.value)}</td><td className="p-2">{number(feature.referenceValue)}</td><td className="whitespace-nowrap p-2">{Math.abs(feature.delta) < 0.000001 ? "接近零" : `${feature.delta > 0 ? "提高" : "降低"} ${Math.abs(feature.delta * 100).toFixed(4)} 个百分点`}</td></tr>)}</tbody></table></div>
          <details className="text-xs leading-6 text-foreground-500"><summary className="cursor-pointer">解释方法与可追溯信息</summary>{explanation.limitations.map(item => <p key={item}>{item}</p>)}<p className="break-all font-mono">模型 SHA-256：{explanation.modelSha256}</p><p className="break-all font-mono">数据 SHA-256：{explanation.sourceSha256}</p></details>
          <p className="text-xs text-foreground-500">原始属性和文件来源见本页；关系图展示实际关联，未计算单条关系的风险贡献。</p>
        </> : <><p className="text-xs text-foreground-500">这条历史预测尚未计算解释。</p><button type="button" disabled={busy} onClick={() => void predict(prediction.modelId)} className="text-xs text-primary-400 disabled:opacity-50">计算该版本的解释</button></>}
        <Link to={assistantLink(prediction.modelId)} className="inline-block text-xs text-primary-400">让智能助手解读此版本 →</Link>
      </section>;
    })}
  </Card>;
}

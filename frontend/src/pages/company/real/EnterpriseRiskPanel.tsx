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
  const voting = models.find((model) => model.id === selected)?.scoreKind === "vote_share";
  useEffect(() => {
    let active = true;
    requestEnterpriseOverview({ datasetId }).then(result => {
      if (active) { setModels(result.models); setSelected(modelId || (result.models.length === 1 ? result.models[0].id : "")); }
    }).catch(cause => { if (active) setError(handleApiError(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [datasetId, modelId]);
  async function predict(identity: string, explain: boolean) {
    setBusy(true); setError("");
    try { await requestPredictModel({ modelId: identity, companyIds: [companyId], explain }); onUpdated(); }
    catch (cause) { setError(handleApiError(cause, {
      MODEL_RESOURCE_NOT_FOUND: "企业不在此模型绑定图内，或模型不存在。请检查企业与模型范围。",
      RISKGNN_COMPANY_NOT_FOUND: "该企业不在此模型绑定图内，当前暂不支持新企业推理。",
      MODEL_EXPLANATION_UNAVAILABLE: "该模型版本暂无可用的特征解释。",
    })); }
    finally { setBusy(false); }
  }
  const assistantLink = (identity: string) => `/chat?${new URLSearchParams({ riskDataset: datasetId, riskModel: identity, riskCompany: companyId })}`;
  return <Card title="企业状态预测与解释" subtitle="模型分数未经校准；请结合模型测试质量、标签含义和来源证据判断。" icon="ri-cpu-line" bodyClassName="space-y-4 p-5">
    {error && <p role="alert" className="text-sm text-danger-500">{error}</p>}
    {loading ? <p role="status" className="text-sm text-foreground-500">正在加载可用模型…</p> : models.length > 0 ? <div className="flex flex-wrap items-end gap-3">
      <label className="text-xs">本数据集的已发布模型<select value={selected} onChange={event => setSelected(event.target.value)} disabled={busy} className="mt-2 block max-w-full rounded-md border border-background-300 bg-background-50 p-2 text-sm"><option value="">请选择模型版本</option>{models.map(model => <option key={model.id} value={model.id}>{model.name} · {model.id.slice(0, 8)}</option>)}</select></label>
      <button type="button" disabled={busy || !selected} onClick={() => void predict(selected, !voting)} className="rounded-md bg-primary-500 px-4 py-2 text-xs text-white disabled:opacity-50">{busy ? "正在预测…" : voting ? "投票预测" : "预测并解释"}</button>
      {selected && <Link to={assistantLink(selected)} className="py-2 text-xs text-primary-400">让智能助手解读 →</Link>}
    </div> : !error && <p className="text-sm text-foreground-500">本数据集暂无已发布模型，请先完成训练和测试，再在工作台发布模型版本。</p>}
    <Link to={`/modeling/models?dataset=${encodeURIComponent(datasetId)}`} className="inline-block text-xs text-primary-400">打开工作台模型管理 →</Link>
    {data.predictions.length === 0 && <p className="text-sm text-foreground-500">该企业尚无已保存的预测结果。</p>}
    {data.predictions.map(prediction => {
      const explanation = prediction.result.explanation;
      const vote = prediction.result.scoreKind === "vote_share";
      const details = prediction.result.voting;
      const sensitivity = prediction.result.votingExplanation;
      return <section key={prediction.modelId} className="space-y-3 rounded-md border border-background-200 p-4">
        <h3 className="text-sm font-medium">{prediction.modelName}</h3>
        <p className="break-all font-mono text-[10px] text-foreground-500">模型版本：{prediction.modelId}</p>
        <p className="text-lg font-semibold">{vote ? "高风险票数占比" : "状态分类分数"} {(prediction.result.probability * 100).toFixed(2)}% <span className="text-sm font-normal">· {vote ? (prediction.result.predictedLabel === 1 ? "判为高风险" : "未判为高风险") : `预测类别 ${prediction.result.predictedLabel}`}</span></p>
        {vote && (details ? <>
          <p className="text-xs text-foreground-500">获得 {details.positiveVotes}/{details.members.length} 张高风险票，至少需 {details.requiredVotes} 张才判为高风险。成员分数达到各自阈值时投高风险票。</p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="成员模型投票明细">
              <thead><tr>{["成员模型", "分数", "阈值", "投票"].map(label => <th key={label} scope="col" className="whitespace-nowrap p-2">{label}</th>)}</tr></thead>
              <tbody>{details.members.map(member => <tr key={member.algorithm} className="border-t border-background-200">
                <th scope="row" className="p-2 font-medium">{member.algorithm}</th>
                <td className="p-2 tabular-nums" title={String(member.score)}>{number(member.score)}</td>
                <td className="p-2 tabular-nums" title={String(member.threshold)}>{number(member.threshold)}</td>
                <td className="whitespace-nowrap p-2">{member.vote === 1 ? "高风险票" : "未投高风险票"}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </> : <p className="text-xs text-foreground-500">这条历史预测暂无投票明细。<button type="button" disabled={busy} onClick={() => void predict(prediction.modelId, false)} className="text-primary-400 disabled:opacity-50">重新预测以获取明细</button></p>)}
        {vote && (sensitivity && details ? <section className="space-y-2">
          <h4 className="text-sm font-medium">特征对投票的影响</h4>
          <p className="text-xs leading-6 text-foreground-500">每次只将一项输入替换为 {sensitivity.referenceCount.toLocaleString()} 家训练企业的中位数，固定模型权重、阈值和关系图。结果反映此参考场景下的敏感性，各项变化不可相加。</p>
          {sensitivity.features.map(feature => {
            const labelChanged = feature.predictedLabelAtReference !== prediction.result.predictedLabel;
            const voteChanged = feature.members.some(member => details.members.find(before => before.algorithm === member.algorithm)?.vote !== member.voteAtReference);
            const scoreChanged = feature.members.some(member => member.delta !== 0);
            let outcome = scoreChanged ? "分数变化，投票不变" : "分数和投票均未变";
            if (voteChanged) outcome = "有成员改票，类别不变";
            if (labelChanged) outcome = feature.predictedLabelAtReference === 1 ? "改判高风险" : "改判为未达高风险门槛";
            return <details key={feature.feature} className="rounded-md border border-background-200 p-3 text-xs">
              <summary className="cursor-pointer leading-6">
                {featureNames[feature.feature] ?? feature.feature} · {number(feature.value)} → {number(feature.referenceValue)}
                {" · "}高风险票 {details.positiveVotes} → {feature.positiveVotesAtReference}
                {" · "}{outcome}
              </summary>
              <ul className="mt-2 space-y-1">
                {feature.members.map(member => {
                  const before = details.members.find(item => item.algorithm === member.algorithm);
                  return <li key={member.algorithm}>
                    {member.algorithm} · 分数 {before ? number(before.score) : "—"} → {number(member.scoreAtReference)}
                    {" · "}变化 {number(-member.delta * 100)} 个百分点 · {member.voteAtReference === 1 ? "高风险票" : "未投高风险票"}
                    {before && before.vote !== member.voteAtReference && "（改票）"}
                  </li>;
                })}
              </ul>
            </details>;
          })}
        </section> : <button type="button" disabled={busy} onClick={() => void predict(prediction.modelId, true)} className="block text-xs text-primary-400 disabled:opacity-50">计算特征对投票的影响</button>)}
        {!vote && <p className="text-xs text-foreground-500">融合分数：{prediction.result.fusedProbability == null ? "—" : `${(prediction.result.fusedProbability * 100).toFixed(2)}%`} · 证据不确定性：{prediction.result.uncertainty == null ? "—" : number(prediction.result.uncertainty)} · 分支冲突度：{prediction.result.conflict == null ? "—" : number(prediction.result.conflict)}</p>}
        {explanation ? <>
          <p className="break-words text-xs leading-6 text-foreground-500">标签定义：{explanation.target}</p>
          <p className="text-xs text-foreground-500">评估时间：{new Date(explanation.evaluatedAt).toLocaleString()} · 测试 ROC-AUC：{typeof explanation.testMetrics.rocAuc === "number" ? explanation.testMetrics.rocAuc.toFixed(4) : "未提供"}</p>
          <div className="rounded-md border border-warning-500/30 bg-warning-500/5 p-3 text-xs leading-6">{explanation.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>
          <h4 className="text-sm font-medium">特征敏感性</h4>
          <p className="text-xs leading-6 text-foreground-500">逐项替换为训练目标企业中位数（{explanation.referenceCount.toLocaleString()} 家），固定其余输入与关系图。变化为原分数减去替换后分数，单位为百分点；不是 SHAP，各项不能相加。</p>
          <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-foreground-500"><tr>{["特征", "模型输入值", "训练参考值", "相对参考值的影响"].map(label => <th key={label} className="whitespace-nowrap p-2 font-medium">{label}</th>)}</tr></thead><tbody>{explanation.features.map(feature => <tr key={feature.feature} className="border-t border-background-200"><td className="p-2">{featureNames[feature.feature] ?? feature.feature}<span className="block font-mono text-[10px] text-foreground-500">{feature.feature}</span></td><td className="p-2">{number(feature.value)}</td><td className="p-2">{number(feature.referenceValue)}</td><td className="whitespace-nowrap p-2">{Math.abs(feature.delta) < 0.000001 ? "接近零" : `${feature.delta > 0 ? "提高" : "降低"} ${Math.abs(feature.delta * 100).toFixed(4)} 个百分点`}</td></tr>)}</tbody></table></div>
          <details className="text-xs leading-6 text-foreground-500"><summary className="cursor-pointer">解释方法与可追溯信息</summary>{explanation.limitations.map(item => <p key={item}>{item}</p>)}<p className="break-all font-mono">模型 SHA-256：{explanation.modelSha256}</p><p className="break-all font-mono">数据 SHA-256：{explanation.sourceSha256}</p></details>
          <p className="text-xs text-foreground-500">原始属性和文件来源见本页；关系图展示实际关联，未计算单条关系的风险贡献。</p>
        </> : !vote && <><p className="text-xs text-foreground-500">这条历史预测尚未计算解释。</p><button type="button" disabled={busy} onClick={() => void predict(prediction.modelId, true)} className="text-xs text-primary-400 disabled:opacity-50">计算该版本的解释</button></>}
        <Link to={assistantLink(prediction.modelId)} className="inline-block text-xs text-primary-400">让智能助手解读此版本 →</Link>
      </section>;
    })}
  </Card>;
}

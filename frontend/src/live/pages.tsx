import { useState, type ReactNode } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import AppShell from '@/components/feature/AppShell';
import { useApi, percent, featureNames, type Listing, type Detail, type Explanation, type Graph, type Evaluation } from './api';
import './style.css';

const link = (id: string, page = 'company') => `/${page}/${encodeURIComponent(id)}`;
function Panel({ title, children }: { title: string; children: ReactNode }) { return <section className="live-panel"><h2>{title}</h2>{children}</section>; }
function Pending({ error, retry }: { error?: string; retry: () => void }) {
  return error ? <div className="live-error" role="alert"><strong>暂时无法读取后端数据</strong><p>{error === 'unknown company ID' ? '该企业不在当前 SMEsD 快照中，请返回企业检索选择有效编号。' : `${error}。请确认本地后端已启动。`}</p><button onClick={retry}>重试</button> <Link to="/search">返回企业检索</Link></div> : <p role="status" className="live-loading">正在读取模型数据…</p>;
}
function Frame({ title, children, id }: { title: string; children: ReactNode; id?: string }) {
  return <AppShell title={title} subtitle="SMEsD 匿名企业实验 · 真实模型推理"><div className="live-root"><div className="live-notice">公开数据集实验；企业名称已匿名。风险概率对应数据集破产标签，不代表未来 12 个月违约概率。</div>{id && <nav className="live-tabs" aria-label="企业分析"><Link to={link(id)}>企业画像</Link><Link to={link(id, 'score')}>评分与解释</Link><Link to={`/graph?id=${encodeURIComponent(id)}`}>关系图</Link><Link to="/search">切换企业</Link></nav>}{children}</div></AppShell>;
}
function Metrics({ value }: { value: Evaluation }) {
  const m = value.metrics.test;
  return <div className="live-stats">{[['测试 AUC', m.roc_auc.toFixed(4)], ['PR-AUC', m.pr_auc.toFixed(4)], ['KS', m.ks.toFixed(4)], ['Brier', m.brier.toFixed(4)]].map(([title, v]) => <div key={title}><span>{title}</span><strong>{v}</strong></div>)}</div>;
}
export function Overview() {
  const api = useApi<Evaluation>('/v1/evaluation');
  return <Frame title="模型实验工作台">{api.data ? <><div className="live-hero"><div><span className="live-eyebrow">COMRISK · SMEsD</span><h2>从匿名企业到可核对的风险结果</h2><p>选择企业，查看模型评分、真实关系及特征影响。</p><Link className="live-button" to="/search">开始企业分析 →</Link></div><div className="live-hero-count"><strong>{api.data.company_count}</strong><span>当前快照企业</span></div></div><Metrics value={api.data}/><div className="live-grid"><Panel title="当前运行模型"><p>{api.data.model} / {api.data.mode} / seed {api.data.seed}</p><p>数据快照：{api.data.dataset}</p><p>后端已返回真实评估数据；输入{api.data.synthetic ? '为合成数据' : '来自公开 SMEsD 数据'}。</p><Link to="/model">查看训练与评估记录 →</Link></Panel><Panel title="演示路径"><ol><li>检索匿名企业编号或行业。</li><li>查看风险概率与验证集选定的分类阈值。</li><li>核对关系边、特征遮蔽解释和真实标签。</li></ol><p>报告生成与授信决策尚未接入。</p></Panel></div></> : <Pending {...api}/>}</Frame>;
}
export function Search() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') || '';
  const offset = Math.max(0, Number(params.get('offset')) || 0);
  const [draft, setDraft] = useState(q);
  const api = useApi<Listing>(`/v1/companies?q=${encodeURIComponent(q)}&offset=${offset}&limit=20`);
  const changePage = (n: number) => setParams({ q, offset: String(n) });
  return <Frame title="企业检索"><Panel title="选择一个真实样本"><form className="live-search" onSubmit={e => { e.preventDefault(); setParams({ q: draft.trim() }); }}><input aria-label="企业编号或行业" placeholder="输入企业编号或行业，如 C00010" value={draft} onChange={e => setDraft(e.target.value)}/><button>检索</button></form>{api.data ? <><p>共 {api.data.total} 家 · {api.data.dataset}</p>{!api.data.items.length ? <p role="status">没有匹配企业，请修改搜索条件。</p> : <div className="live-table-wrap"><table><thead><tr><th>企业编号</th><th>行业</th><th>风险概率</th><th>分类结果</th><th>操作</th></tr></thead><tbody>{api.data.items.map(c => <tr key={c.id}><td><Link to={link(c.id)}>{c.id}</Link><small>匿名企业 · {c.split}</small></td><td>{c.community}</td><td>{percent(c.risk_probability)}</td><td><span className={c.predicted_label ? 'live-risk' : 'live-normal'}>{c.predicted_label ? '预测正例' : '预测负例'}</span></td><td><Link to={link(c.id, 'score')}>查看评分 →</Link></td></tr>)}</tbody></table></div>}<div className="live-pager"><button disabled={offset === 0} onClick={() => changePage(Math.max(0, offset - 20))}>上一页</button><span>第 {Math.floor(offset / 20) + 1} 页</span><button disabled={offset + 20 >= api.data.total} onClick={() => changePage(offset + 20)}>下一页</button></div></> : <Pending {...api}/>}</Panel></Frame>;
}
export function Company() {
  const { id = '' } = useParams();
  const api = useApi<Detail>(`/v1/companies/${encodeURIComponent(id)}`);
  return <Frame title={`企业画像 · ${id}`} id={id}>{api.data ? <><div className="live-grid"><Panel title={api.data.name}><p>编号：{id}</p><p>行业：{api.data.community}</p><p>样本划分：{api.data.split}</p><p>司法事件：{api.data.event_count} 条</p><Link className="live-button" to={link(id, 'score')}>查看模型评分 →</Link></Panel><Panel title="模型输入特征">{Object.entries(api.data.features).map(([k, v]) => <div className="live-kv" key={k}><span>{featureNames[k] || k}</span><strong>{v === null ? '缺失' : v.toFixed(3)}</strong></div>)}<p>资本为 log1p 转换后的模型输入值，非原始货币金额。数据不提供企业真实名称、国家或财报。</p></Panel></div><Panel title="司法事件编码"><p>保留原始类别编码，不推测案由、法院名称和裁判内容。最多展示 20 条。</p><div className="live-table-wrap"><table><thead><tr><th>案由编码</th><th>法院编码</th><th>结果编码</th><th>相对时间（月）</th></tr></thead><tbody>{api.data.events.map((e, i) => <tr key={i}><td>{e.cause}</td><td>{e.court}</td><td>{e.result}</td><td>{e.age_months}</td></tr>)}</tbody></table>{!api.data.events.length && <p>该样本没有司法事件。</p>}</div></Panel></> : <Pending {...api}/>}</Frame>;
}
function ExplanationPanel({ id }: { id: string }) {
  const api = useApi<Explanation>(`/v1/explain/${encodeURIComponent(id)}`);
  return <Panel title="特征遮蔽分析">{api.data ? <><p>将单个数值特征替换为训练均值，比较概率变化。正值表示原特征使当前预测更高；负值表示更低。单位：百分点。</p><p>这不是 SHAP；影响值不能相加，也不表示因果关系。这里只解释数值特征，不覆盖司法和关系分支。</p>{api.data.features.map(f => <div className="live-effect" key={f.feature}><span>{featureNames[f.feature] || f.feature}</span><div><i style={{ width: `${Math.min(100, Math.abs(f.probability_delta) * 100)}%`, background: f.probability_delta >= 0 ? '#b45309' : '#2563eb' }}/></div><strong>{f.probability_delta > 0 ? '+' : ''}{(f.probability_delta * 100).toFixed(3)}</strong></div>)}</> : <Pending {...api}/>}</Panel>;
}
export function Score() {
  const { id = '' } = useParams();
  const company = useApi<Detail>(`/v1/companies/${encodeURIComponent(id)}`);
  const evaluation = useApi<Evaluation>('/v1/evaluation');
  return <Frame title={`评分与解释 · ${id}`} id={id}>{company.data && evaluation.data ? <><div className="live-grid"><Panel title="模型风险概率"><div className="live-probability">{percent(company.data.risk_probability)}</div><p>{company.data.predicted_label ? '预测正例（破产标签 = 1）' : '预测负例（破产标签 = 0）'}</p><p>分类阈值：{percent(evaluation.data.threshold)}，由验证集选定。</p><p>演示信用分：{company.data.credit_score} / 850（线性映射，未经信用量表验证）。</p></Panel><Panel title="可核对的模型记录"><p>模型：{evaluation.data.model}</p><p>版本配置：{evaluation.data.mode} · seed {evaluation.data.seed}</p><p>数据：{company.data.dataset}</p><details><summary>展开样本真实标签（仅用于评估）</summary><p>真实标签：{company.data.observed_label ?? '无标签'}；{company.data.observed_label === null ? '无法比较' : company.data.observed_label === company.data.predicted_label ? '本次分类正确' : '本次分类错误'}。标签不是推理输入。</p></details><Link to={`/graph?id=${encodeURIComponent(id)}`}>核对企业关系 →</Link></Panel></div><ExplanationPanel key={id} id={id}/></> : <Pending error={company.error || evaluation.error} retry={() => { company.retry(); evaluation.retry(); }}/>}</Frame>;
}
export function GraphPage() {
  const [params] = useSearchParams();
  const id = params.get('id') || '';
  return id ? <GraphDetail key={id} id={id}/> : <Frame title="企业关系图"><Panel title="先选择企业"><Link to="/search">前往企业检索 →</Link></Panel></Frame>;
}
function GraphDetail({ id }: { id: string }) {
  const api = useApi<Graph>(`/v1/companies/${encodeURIComponent(id)}/graph`);
  const [selected, setSelected] = useState(id);
  const g = api.data;
  const neighbors = g?.nodes.filter(n => n.id !== id) || [];
  const positions = new Map([[id, { x: 400, y: 220 }], ...neighbors.map((n, i) => [n.id, { x: 400 + 290 * Math.cos(i * 2 * Math.PI / neighbors.length), y: 220 + 160 * Math.sin(i * 2 * Math.PI / neighbors.length) }] as const)]);
  const node = g?.nodes.find(n => n.id === selected);
  return <Frame title={`企业关系图 · ${id}`} id={id}>{g ? <Panel title="真实一跳关系"><p>共 {g.total_edges} 条关联边，当前展示 {g.edges.length} 条{g.truncated ? '（已截断）' : ''}。箭头保持原数据方向；关系编码不推测为担保或供应链。同一对节点的多种关系可能重叠，具体方向与类型见下表。</p>{!g.edges.length ? <p>当前快照中该企业没有一跳关系。</p> : <svg className="live-graph" viewBox="0 0 800 440" role="img" aria-label="企业一跳关系网络"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/></marker></defs>{g.edges.map((e, i) => { const a = positions.get(e.source)!; const b = positions.get(e.target)!; const d = Math.hypot(b.x - a.x, b.y - a.y) || 1; const ux = (b.x - a.x) / d; const uy = (b.y - a.y) / d; const start = e.source === id ? 28 : 17; const end = e.target === id ? 28 : 17; return <line key={i} x1={a.x + ux * start} y1={a.y + uy * start} x2={b.x - ux * end} y2={b.y - uy * end} stroke="#cbd5e1" strokeWidth="1.5" markerEnd="url(#arrow)"/>; })}{g.nodes.map(n => { const p = positions.get(n.id)!; return <g key={n.id} role="button" tabIndex={0} aria-label={`查看节点 ${n.id}`} onClick={() => setSelected(n.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(n.id); } }} style={{ cursor: 'pointer' }}><circle cx={p.x} cy={p.y} r={n.id === id ? 25 : 14} fill={n.id === id ? '#2563eb' : n.kind === 'person' ? '#a16207' : '#64748b'} stroke={selected === n.id ? '#0f172a' : 'white'} strokeWidth="2"/><text x={p.x} y={p.y + 35} textAnchor="middle" fontSize="11">{n.id}</text></g>; })}</svg>}{node && <div className="live-notice">选中节点：{node.id} · {node.kind === 'company' ? '企业' : '个人'} · {node.community} {node.kind === 'company' && <Link to={link(node.id, 'score')}>查看评分 →</Link>}</div>}<div className="live-table-wrap"><table><thead><tr><th>来源</th><th>目标</th><th>关系编码</th><th>模型边权</th></tr></thead><tbody>{g.edges.map((e, i) => <tr key={i}><td>{e.source}</td><td>{e.target}</td><td>{e.relation}</td><td>{e.weight.toFixed(3)}</td></tr>)}</tbody></table></div></Panel> : <Pending {...api}/>}</Frame>;
}
export function Model() {
  const api = useApi<Evaluation>('/v1/evaluation');
  return <Frame title="模型与评估">{api.data ? <><Metrics value={api.data}/><Panel title="已保存的训练评估记录"><p>{api.data.model} · {api.data.mode} · seed {api.data.seed} · 最佳 epoch {api.data.best_epoch}</p><p>结构按多种子平均验证 BCE 选定，分类阈值与截距校准使用验证集；测试集仅用于报告效果。</p><div className="live-table-wrap"><table><thead><tr><th>划分</th><th>企业数</th><th>正例数</th><th>AUC</th><th>PR-AUC</th><th>KS</th><th>Brier</th></tr></thead><tbody>{Object.entries(api.data.metrics).map(([name, m]) => <tr key={name}><td>{name}</td><td>{m.n}</td><td>{m.positives}</td><td>{m.roc_auc.toFixed(4)}</td><td>{m.pr_auc.toFixed(4)}</td><td>{m.ks.toFixed(4)}</td><td>{m.brier.toFixed(4)}</td></tr>)}</tbody></table></div><p>当前选定配置：{api.data.mode}。{api.data.mode === 'no_hyper' ? '未启用超图分支。' : ''}当前结果不是东南亚比赛数据实测；尚不能保证严格时间点有效性。</p><a href="/api/v1/evaluation" target="_blank" rel="noreferrer">打开原始评估 JSON ↗</a></Panel></> : <Pending {...api}/>}</Frame>;
}
export function Unavailable() { return <Frame title="功能尚未接入"><Panel title="当前版本范围"><p>本次已接入企业检索、画像、评分、关系图和模型评估。报告生成、授信决策与批量上传尚未接入真实后端。</p><Link to="/search">返回企业检索 →</Link></Panel></Frame>; }

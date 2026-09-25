export type RiskLevel = "low" | "medium" | "high";

export type ServiceStatus = "operational" | "degraded" | "down";

export interface Company {
  id: string;
  nameCn: string;
  nameEn: string;
  regNo: string;
  country: string;
  countryEn?: string;
  region: string;
  regionEn?: string;
  sector: string;
  sectorEn?: string;
  countryFlag: string;
  industry: string;
  industryEn?: string;
  creditScore: number;
  riskLevel: RiskLevel;
  defaultProb: number;
  creditLimit: string;
  updatedAt: string;
  tags: string[];
  tagsEn?: string[];
}

export interface TrendPoint {
  date: string;
  evaluations: number;
  highRisk: number;
}

export interface RiskDistributionItem {
  level: RiskLevel;
  label: string;
  value: number;
}

export interface SystemService {
  name: string;
  desc: string;
  status: ServiceStatus;
  latency: string;
  uptime: string;
}

export interface PresetCase {
  id: string;
  companyId: string;
  title: string;
  summary: string;
  riskLevel: RiskLevel;
}

export interface OverviewStats {
  coveredCompanies: number;
  coveredDelta: string;
  todayEvaluations: number;
  todayDelta: string;
  highRiskCount: number;
  highRiskDelta: string;
  avgCreditScore: number;
  avgDelta: string;
}

export interface ModelMetric {
  key: string;
  label: string;
  value: string;
  hint: string;
}

export interface CompanyFacts {
  established: string;
  registeredCapital: string;
  paidInCapital: string;
  legalPerson: string;
  actualController: string;
  controllerStake: string;
  employees: string;
  listed: string;
  ratingAgency: string;
  mainBanks: string;
  settlement: string;
  revenue: string;
  netMargin: string;
}

/** 工商信息的英文副本（仅用于展示，缺失时回退中文）。 */
export interface CompanyFactsEn {
  registeredCapital?: string;
  paidInCapital?: string;
  legalPerson?: string;
  actualController?: string;
  controllerStake?: string;
  employees?: string;
  listed?: string;
  ratingAgency?: string;
  mainBanks?: string;
  settlement?: string;
  revenue?: string;
  netMargin?: string;
}

export type TimelineType =
  | "equity"
  | "legal"
  | "address"
  | "finance"
  | "risk"
  | "award";

export type TimelineImpact = "positive" | "neutral" | "negative";

export interface TimelineEvent {
  id: string;
  date: string;
  type: TimelineType;
  title: string;
  titleEn?: string;
  desc: string;
  descEn?: string;
  impact: TimelineImpact;
}

export interface RiskFlag {
  id: string;
  label: string;
  labelEn?: string;
  level: RiskLevel;
  category: string;
  categoryEn?: string;
  desc: string;
  descEn?: string;
  source: string;
  detectedAt: string;
}

export interface FiveCDimension {
  key: string;
  label: string;
  en: string;
  weight: number;
  score: number;
  note: string;
  noteEn?: string;
}

export interface RelatedParty {
  id: string;
  name: string;
  nameEn?: string;
  relation: string;
  relationEn?: string;
  exposure: string;
  exposureEn?: string;
  riskLevel: RiskLevel;
}

export interface CompanyProfile {
  facts: CompanyFacts;
  factsEn?: CompanyFactsEn;
  summary: string;
  summaryEn?: string;
  timeline: TimelineEvent[];
  riskFlags: RiskFlag[];
  fiveC: FiveCDimension[];
  relatedParties: RelatedParty[];
}

export type GraphNodeType =
  | "company"
  | "owner"
  | "subsidiary"
  | "supplier"
  | "guarantor"
  | "client"
  | "counterparty"
  | "person"
  | "bank"
  | "fund";

export type GraphEdgeType =
  | "equity"
  | "control"
  | "guarantee"
  | "supply"
  | "trade"
  | "loan";

export interface GraphNode {
  id: string;
  label: string;
  type: GraphNodeType;
  riskLevel: RiskLevel;
  hop: number;
  relation: string;
  exposure: string;
  industry?: string;
  country?: string;
  companyId?: string;
  note?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: GraphEdgeType;
  label: string;
  riskFlow: boolean;
  strength: number;
}

export interface GraphData {
  rootId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface RiskPath {
  nodeId: string;
  label: string;
  riskLevel: RiskLevel;
  hops: number;
  chain: string[];
}

export interface ShapFeature {
  id: string;
  label: string;
  category: string;
  value: string;
  contribution: number;
  desc: string;
}

export interface CommunityBenchmark {
  key: string;
  label: string;
  tag: string;
  sampleSize: number;
  avgScore: number;
  avgDefaultProb: number;
  percentile: number;
  goodRate: number;
  diff: number;
}

export interface ScoreDetail {
  baseValue: number;
  finalScore: number;
  grade: string;
  gradeNote: string;
  riskPercentile: number;
  defaultProb: number;
  pdBase: number;
  pdDelta: number;
  confidence: number;
  modelVersion: string;
  evaluatedAt: string;
  positiveCount: number;
  negativeCount: number;
  features: ShapFeature[];
  benchmarks: CommunityBenchmark[];
}

export type EvidenceType =
  | "graph"
  | "feature"
  | "snapshot"
  | "fact"
  | "benchmark"
  | "timeline"
  | "flag";

export interface Evidence {
  id: string;
  number: number;
  type: EvidenceType;
  title: string;
  snippet: string;
  source: string;
  metric?: string;
  confidence: number;
  capturedAt: string;
  refPath?: string;
  refLabel?: string;
}

export interface ReportSentence {
  id: string;
  text: string;
  citations: number[];
}

export interface ReportParagraph {
  id: string;
  sentences: ReportSentence[];
}

export interface ReportSection {
  id: string;
  index: number;
  title: string;
  icon: string;
  paragraphs: ReportParagraph[];
}

export interface ReportDoc {
  id: string;
  title: string;
  subtitle: string;
  generatedAt: string;
  modelVersion: string;
  wordCount: number;
  sentenceCount: number;
  sections: ReportSection[];
  evidence: Evidence[];
}

export type DecisionOutcome = "approve" | "conditional" | "reject";

export interface CreditLimitBand {
  key: string;
  label: string;
  value: number;
  display: string;
  note: string;
  emphasis: boolean;
}

export interface LimitFactor {
  id: string;
  label: string;
  detail: string;
  amount: number;
  display: string;
  positive: boolean;
}

export interface DecisionTerm {
  key: string;
  label: string;
  value: string;
  note: string;
  icon: string;
  tone: "primary" | "accent" | "secondary";
}

export interface MitigationMeasure {
  id: string;
  title: string;
  detail: string;
  icon: string;
  requirement: "standard" | "recommended" | "required";
}

export type DecisionRuleCategory =
  | "准入"
  | "额度"
  | "账期"
  | "担保"
  | "国别"
  | "模型"
  | "监控";

export type DecisionRuleSeverity = "pass" | "warn" | "block";

export interface DecisionRule {
  id: string;
  code: string;
  name: string;
  category: DecisionRuleCategory;
  categoryEn?: string;
  severity: DecisionRuleSeverity;
  condition: string;
  actual: string;
  action: string;
  desc: string;
}

export interface DecisionDoc {
  id: string;
  outcome: DecisionOutcome;
  outcomeLabel: string;
  outcomeNote: string;
  symbol: string;
  limitLabel: string;
  creditLimit: string;
  limitNumeric: number;
  baseLimit: string;
  baseRatio: number;
  adjustmentDisplay: string;
  adjustmentPositive: boolean;
  bands: CreditLimitBand[];
  factors: LimitFactor[];
  terms: DecisionTerm[];
  mitigations: MitigationMeasure[];
  rules: DecisionRule[];
  hitCount: number;
  warnCount: number;
  blockCount: number;
  passCount: number;
  approver: string;
  decidedAt: string;
  validUntil: string;
  modelVersion: string;
}

export interface EvalMetric {
  key: string;
  label: string;
  fullLabel: string;
  value: number;
  display: string;
  prev: number;
  delta: number;
  deltaDisplay: string;
  ci: number;
  ciRange: string;
  target: number;
  targetDisplay: string;
  higherBetter: boolean;
  status: "pass" | "watch";
  hint: string;
  desc: string;
}

export interface CalibrationBin {
  label: string;
  center: number;
  calibrated: number;
  raw: number;
  count: number;
}

export interface CalibrationCurve {
  bins: CalibrationBin[];
  ece: number;
  rawEce: number;
  mce: number;
  brier: number;
  total: number;
}

export interface AblationRow {
  id: string;
  label: string;
  featureCount: number;
  auc: number;
  ks: number;
  aucDrop: number;
  ksDrop: number;
  importance: number;
  note: string;
}

export interface AblationStudy {
  baselineAuc: number;
  baselineKs: number;
  rows: AblationRow[];
}

export type ExtrapolationCohort = "in" | "near" | "far";

export interface ExtrapolationRow {
  id: string;
  region: string;
  short: string;
  cohort: ExtrapolationCohort;
  sampleSize: number;
  auc: number;
  ks: number;
  aucDecay: number;
  ksDecay: number;
  psi: number;
  decision: string;
}

export interface ExtrapolationStudy {
  baselineAuc: number;
  baselineKs: number;
  rows: ExtrapolationRow[];
}

export interface EvalDashboard {
  modelVersion: string;
  validatedAt: string;
  trainedAt: string;
  datasetSize: number;
  featureCount: number;
  positiveRate: number;
  splitRatio: string;
  metrics: EvalMetric[];
  calibration: CalibrationCurve;
  ablation: AblationStudy;
  extrapolation: ExtrapolationStudy;
}

export interface ReproduceStep {
  label: string;
  detail: string;
  durationMs: number;
}

export interface ReproduceRun {
  target: string;
  title: string;
  subtitle: string;
  runId: string;
  seed: string;
  snapshot: string;
  sampleSize: number;
  engine: string;
  startedAt: string;
  duration: string;
  focusLabel: string;
  focusValue: string;
  focusNote: string;
  steps: ReproduceStep[];
  logs: string[];
}

export type BatchRowStatus = "ok" | "review" | "unmatched";

export interface BatchRow {
  id: string;
  rowNo: number;
  rawName: string;
  matched: boolean;
  duplicate: boolean;
  companyId?: string;
  nameCn: string;
  nameEn: string;
  country: string;
  countryEn?: string;
  region: string;
  sector: string;
  industry: string;
  industryEn?: string;
  creditScore: number;
  grade: string;
  riskLevel: RiskLevel;
  defaultProb: number;
  creditLimit: string;
  outcome: string;
  status: BatchRowStatus;
  issues: string[];
  rank: number | null;
}

export interface BatchRiskCount {
  level: RiskLevel;
  label: string;
  labelEn?: string;
  count: number;
}

export interface BatchSummary {
  total: number;
  matched: number;
  unmatched: number;
  duplicate: number;
  review: number;
  highRisk: number;
  avgScore: number;
  countries: number;
  riskDistribution: BatchRiskCount[];
}

export interface BatchRoster {
  fileName: string;
  fileNameEn?: string;
  source: "sample" | "file";
  importedAt: string;
  rawNames: string[];
  valid: number;
  invalid: number;
}

export interface BatchRun {
  id: string;
  modelVersion: string;
  startedAt: string;
  duration: string;
  scanned: number;
  steps: ReproduceStep[];
}

export interface ModelIdentity {
  name: string;
  codeName: string;
  version: string;
  algorithm: string;
  task: string;
  status: RiskLevel;
  statusLabel: string;
  owner: string;
  releasedAt: string;
  validatedAt: string;
  summary: string;
  nameEn?: string;
  algorithmEn?: string;
  taskEn?: string;
  statusLabelEn?: string;
  ownerEn?: string;
  summaryEn?: string;
}

export interface ModelSpec {
  label: string;
  value: string;
  icon: string;
  labelEn?: string;
  valueEn?: string;
}

export interface PipelineStep {
  key: string;
  label: string;
  desc: string;
  icon: string;
  labelEn?: string;
  descEn?: string;
}

export interface TrainingFeatureGroup {
  key: string;
  label: string;
  count: number;
  share: number;
  labelEn?: string;
}

export interface ModelTrainingData {
  sampleSize: number;
  timeWindow: string;
  countries: number;
  featureCount: number;
  featureGroups: number;
  positiveRate: string;
  labelDefinition: string;
  splitRatio: string;
  sources: string[];
  groups: TrainingFeatureGroup[];
  note: string;
  timeWindowEn?: string;
  positiveRateEn?: string;
  labelDefinitionEn?: string;
  splitRatioEn?: string;
  sourcesEn?: string[];
  noteEn?: string;
}

export interface ModelVersionEntry {
  version: string;
  date: string;
  auc: number;
  ks: number;
  headline: string;
  changes: string[];
  current: boolean;
  headlineEn?: string;
  changesEn?: string[];
}

export interface DriftMetric {
  key: string;
  label: string;
  psi: number;
  status: RiskLevel;
  note: string;
  labelEn?: string;
  noteEn?: string;
}

export interface DriftPoint {
  date: string;
  psi: number;
  dateEn?: string;
}

export interface ModelGovernanceItem {
  id: string;
  title: string;
  desc: string;
  icon: string;
  titleEn?: string;
  descEn?: string;
}
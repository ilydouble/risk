import type { components } from "@/shared/api/generated/schema";

export type ModelingDataset = components["schemas"]["DatasetDTO"];
export type ModelingExperiment = components["schemas"]["ExperimentDTO"];

export interface FeatureDefinition {
  name: string;
  kind: "numeric" | "categorical";
  group: string;
  description?: string;
  recommended?: boolean;
}

export interface BundleManifest {
  schemaVersion: 1;
  datasetName: string;
  taskType: "loan_application" | "entity_snapshot";
  sampleUnit: "loan_application" | "entity_snapshot";
  target: {
    name: string;
    positiveValue: string | number;
    predictionWindowDays?: number | null;
    businessDefinition: string;
  };
  features: FeatureDefinition[];
  files: Record<string, { path: string; format: string; sizeBytes: number; sha256: string } | null>;
  graph?: {
    snapshotMode: string;
    snapshotDefinition: string;
    staticExperimentOnly: boolean;
  } | null;
}

export interface DatasetAnalysisView {
  quality: {
    rowCount: number;
    columnCount: number;
    duplicateSampleIds: number;
    columns: Array<{
      name: string;
      kind: string;
      group: string;
      missingCount: number;
      missingRate: number;
      uniqueCount: number;
      constant: boolean;
      highCardinality: boolean;
    }>;
  };
  splits: Record<string, { rows: number; positives: number; positiveRate: number; entities: number }>;
  signals: Array<{
    name: string;
    kind: string;
    group: string;
    univariateAuc: number | null;
    iv: number | null;
    mutualInformation: number | null;
  }>;
  drift: Record<string, Array<{ name: string; psi: number | null }>>;
  correlations: Array<{ left: string; right: string; correlation: number }>;
  leakageWarnings: Array<{ feature: string; reason: string }>;
  graph: Record<string, unknown> & { available: boolean };
  excludedRawPreview: boolean;
}

export interface MetricView {
  rocAuc: number;
  prAuc: number;
  ks: number;
  brier: number;
  precision: number;
  recall: number;
  f1: number;
  threshold: number;
  confusion: Record<string, number>;
}

export interface VariantResult {
  name: string;
  status: string;
  metrics: { validation: MetricView; test: MetricView };
  explainability: {
    type: string;
    items?: Array<{ feature: string; value: number }>;
    relationSelfGateMean?: number;
    hyperedgeTypeWeights?: number[];
  };
  configuration: Record<string, string | number | boolean>;
  durationSeconds: number;
}

export interface ExperimentResultsView {
  taskType: "loan_application" | "entity_snapshot";
  targetName: string;
  targetDefinition: string;
  variants: VariantResult[];
  disclaimer: string;
}

export function manifestOf(dataset: ModelingDataset) {
  return dataset.manifest as unknown as BundleManifest | null;
}

export function analysisOf(dataset: ModelingDataset) {
  return dataset.analysis as unknown as DatasetAnalysisView | null;
}

export function resultsOf(experiment: ModelingExperiment) {
  return experiment.results as unknown as ExperimentResultsView;
}

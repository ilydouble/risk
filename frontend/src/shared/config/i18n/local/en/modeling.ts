export default {
  modeling: {
    eyebrow: "Metadata-driven Risk Modeling", title: "Risk Modeling Workbench",
    subtitle: "Upload a standard ZIP produced by an external adapter. A local worker analyzes data, selects features, trains the model ladder, and evaluates ablations.",
    retry: "Refresh", loading: "Loading…",
    empty: "No standard bundles yet. Generate a Bundle v1 ZIP with an external adapter first.",
    datasets: "Bundles", experiments: "Experiments",
    steps: { data: "Bundle", quality: "Analysis", build: "Build", evaluate: "Evaluation" },
    task: { loan_application: "Loan application risk", entity_snapshot: "Entity operating risk", legacy_tabular: "Legacy tabular data" },
    status: { pending_upload: "Waiting for upload", queued: "Queued", running: "Running", ready: "Analyzed", completed: "Completed", failed: "Failed", legacy: "Legacy read-only" },
    welcome: { title: "Start with a standard bundle", subtitle: "The workbench does not map customer fields. It accepts Bundle v1 with materialized samples, target, splits, and graph snapshots." },
    upload: { title: "Upload standard bundle", subtitle: "Direct RustFS upload and asynchronous validation", drop: "Drop a ZIP or click to choose", limit: "Bundle v1 · 512 MB · CSV / Parquet", name: "Dataset name", namePlaceholder: "Example: application risk sample v1", action: "Upload and queue analysis", uploading: "Uploading…", queueing: "Creating analysis job…" },
    bundle: { title: "Bundle manifest", schema: "Contract", task: "Task semantics", status: "Status", rows: "Samples", target: "Target definition", positive: "Positive class", window: "Prediction window", files: "Files", staticWarning: "This bundle declares a static graph experiment and must not be described as strict future prediction." },
    analysis: { views: { quality: "Quality", signal: "Feature signals", drift: "Split drift", graph: "Graph" }, rows: "Samples", columns: "Columns", duplicates: "Duplicate sample IDs", leakage: "Leakage hints", fields: "Field profiles", field: "Field", group: "Group", type: "Type", missing: "Missing", unique: "Unique", leakageHints: "Potential leakage", signalTitle: "Training-only univariate signals", graphTitle: "Graph profile", noGraph: "No valid graph components; only tabular models are available.", noRawPreview: "Raw customer rows are neither stored nor displayed." },
    builder: { title: "Build comparison experiment", subtitle: "Run baselines, graph statistics and GNN ablations on fixed splits", name: "Experiment name", target: "Target", seed: "Random seed", featureMode: "Feature mode", recommended: "Recommended", manual: "Manual", models: "Model ladder", events: "Event encoder", relations: "Relation propagation", hyperedges: "Hypergraph propagation", requiresGraph: "Requires valid nodes and relations", requiresHyper: "Requires hyperedges", method: "Imputation, scaling, vocabularies and selection fit only on train. Validation drives early stopping and thresholds; test is final reporting only.", run: "Queue experiment", queueing: "Creating job…" },
    result: { completed: "Experiment completed", comparison: "Model ladder and ablations", duration: "Duration", threshold: "Threshold metrics", explainability: "Explainability", relationGate: "Self-risk gate mean", hyperWeights: "Hyperedge type weights" },
  },
};

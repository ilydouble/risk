export default {
  "modeling": {
    "title": "Model workbench",
    "subtitle": "Upload data, inspect quality and splits, then train, test and publish an available model configuration.",
    "disclaimer": "smoke-v1 real subset experiment: 2,000 labeled targets, a fixed static graph and CPU training. Scores reflect Singapore corporate distress labels, not credit default probability. Two epochs validate the workflow only.",
    "refresh": "Refresh",
    "loading": "Loading…",
    "scope": "Only your datasets, runs and models are shown. Legacy Bundle records remain in the database and are not converted.",
    "tabs": {
      "dataset": "Datasets",
      "run": "Experiments",
      "model": "Model versions"
    },
    "errors": {
      "unavailable": "Model service unavailable. Please retry later.",
      "notReady": "Wait for dataset validation to complete.",
      "state": "This action is unavailable in the current state.",
      "missing": "Company or model resource not found.",
      "file": "Invalid ZIP file or resource limits exceeded.",
      "incompatible": "The selected model configuration does not support this dataset protocol."
    },
    "upload": {
      "title": "Upload a training dataset",
      "pick": "Choose a ZIP dataset",
      "note": "Supports comrisk_export and Bundle v1, up to 512 MiB. The server validates the selected protocol; scripts in archives are never executed.",
      "progress": "Uploading",
      "action": "Upload and validate",
      "verifiedFiles": "Server-verified file index"
    },
    "name": "Dataset name",
    "epochs": "Epochs",
    "train": "Create experiment",
    "cancelling": "Cancelling",
    "cancel": "Cancel experiment",
    "rerun": "Run again",
    "trainLoss": "Training loss",
    "validationLoss": "Validation loss",
    "attempt": "Attempt",
    "report": "Independent test report",
    "reportNote": "The chosen checkpoint is reloaded in a fresh process and evaluated on the frozen test split. Validation selects the checkpoint.",
    "publish": "Publish immutable model version",
    "events": "Execution events and diagnostics",
    "emptyRun": "Select an experiment or create one from a validated dataset.",
    "modelNote": "This version binds a tested model bundle and dataset fingerprint. Publishing does not switch a production model.",
    "download": "Download complete model",
    "predict": "Predict companies",
    "predictNote": "Only IDs in the model graph are supported, up to 32 per request. Input order is preserved.",
    "enterpriseIds": "Company IDs (newlines or commas)",
    "fillExamples": "Use model company examples",
    "probability": "Distress classification score",
    "label": "Predicted label",
    "emptyModel": "Publish a model after an experiment passes independent testing.",
    "retired": "Legacy benchmark retired",
    "retiredNote": "The SMEsD benchmark has been replaced by the independent RiskGNN workbench. Historical data and local artifacts are retained.",
    "status": {
      "pending_upload": "Awaiting upload",
      "queued": "Queued",
      "running": "Running",
      "ready": "Validated",
      "failed": "Failed",
      "cancelled": "Cancelled",
      "completed": "Completed",
      "starting": "Starting",
      "validating": "Full validation",
      "preparing": "Preparing subset",
      "training": "Training",
      "testing": "Independent test",
      "uploading": "Uploading artifacts",
      "expired": "Lease expired",
      "retrying": "Awaiting retry"
    },
    "metrics": {
      "rocAuc": "ROC-AUC",
      "prAuc": "PR-AUC",
      "ks": "KS",
      "brier": "Brier",
      "f1": "F1",
      "count": "Test samples",
      "positiveCount": "Test positives",
      "precision": "Precision",
      "recall": "Recall"
    },
    "confusion": "Confusion matrix (rows: actual; columns: predicted)",
    "modelChoice": "Model configuration",
    "catalog": "Model capabilities",
    "available": "Training and publication available",
    "analysisOnly": "Analysis is complete. No training configuration is connected for this dataset protocol yet.",
    "dataFormat": "Dataset protocol",
    "models": {
      "riskgnn-node-edge": "RiskGNN · node + edge",
      "riskgnn-node-only": "RiskGNN · node only",
      "comrisk-baseline": "ComRisk baseline",
      "riskgnn-plus": "RiskGNN+"
    },
    "capabilityReasons": {
      "ARTIFACT_ADAPTER_PENDING": "Artifact adapter pending",
      "RESEARCH_VALIDATION_PENDING": "Research validation pending"
    },
    "analysis": {
    "iv": "IV",
    "mutualInformation": "Mutual information",
      "title": "Dataset analysis",
      "rows": "rows",
      "driftSample": "Rows sampled for PSI",
      "splitCounts": "Samples · positive rate",
      "feature": "Feature",
      "missing": "Missing rate",
      "unique": "Distinct values",
      "auc": "Training univariate AUC",
      "validationPsi": "Validation PSI",
      "testPsi": "Test PSI",
      "constant": "constant",
      "warnings": "Features to review",
      "correlations": "Training feature correlations",
      "graph": "Graph summary",
      "scopes": {
        "full": "Computed from all uploaded samples",
        "full_quality_sampled_drift": "Full quality scan; PSI uses a fixed sample of up to 5,000 rows per split"
      },
      "splits": {
        "train": "Training",
        "validation": "Validation",
        "test": "Test"
      },
      "warningCodes": {
        "SUSPICIOUS_FEATURE_NAME": "Name may indicate an ID or post-outcome information",
        "NEAR_PERFECT_TRAINING_SIGNAL": "Near-perfect training signal; review for leakage",
        "REVIEW_FEATURE": "Review the feature definition"
      }
    },
    "profile": {
      "title": "Experiment profile",
      "target": "Prediction target",
      "sgTarget": "Singapore registration distress / liquidation proxy",
      "selection": "Checkpoint selection",
      "bestEpoch": "Selected epoch",
      "features": "Actual features",
      "preprocessing": "Preprocessing fit split",
      "provenance": "Data and implementation versions",
      "datasetHash": "Dataset SHA-256",
      "sourceHash": "Model and adapter source SHA-256",
      "dependencies": "Dependencies",
      "criteria": {
        "validation_loss": "Validation loss"
      }
    }
  }
};

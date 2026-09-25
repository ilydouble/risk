export default {
  batch: {
    page: {
      title: "Batch Evaluation",
      subtitle:
        "Upload a company list → score and rank in bulk → export the result table, completing a full credit pre-screen in one pass",
      backToOverview: "Back to overview",
      exportPdf: "Export PDF",
      exportResult: "Export result table",
    },
    steps: {
      upload: "Upload company list",
      score: "Batch score & rank",
      export: "Export result table",
    },
    toasts: {
      parsed: "List parsed, you can start batch scoring",
      sampleLoaded: "Sample list loaded, you can start batch scoring",
      exported: "Result table exported as a CSV file",
    },
    ready: {
      title: "List ready · {{count}} records",
      desc: "Each row will be matched against the company library and the model will output credit score, grade, default probability and recommendation, then rank by credit score.",
      start: "Start batch scoring",
    },
    run: {
      doneTitle: "Batch scoring complete",
      runningTitle: "Batch scoring & ranking",
      doneDesc:
        "Scored, graded and ranked {{count}} entities; the result table is ready",
      runningDesc:
        "Running the parse → match → score → rank pipeline in sequence",
      batchId: "Batch id",
      model: "Scoring model",
      scale: "List size",
      startedAt: "Started at",
      scaleUnit: "{{count}}",
    },
    summary: {
      total: "Total records",
      matched: "Matched entities",
      unmatched: "Pending onboarding",
      avgScore: "Average credit score",
      highRisk: "High-risk entities",
      countries: "Countries / regions",
      unitRecord: "",
      unitCompany: "",
      unitScore: "pts",
      unitCountry: "",
      distributionTitle: "Risk level distribution",
      uniqueNote: "{{count}} unique entities",
      companyUnit: "{{count}}",
      notesTitle: "Result handling notes",
      noteMatched:
        "{{matched}} matched, of which {{duplicate}} de-duplicated, ranked by credit score desc",
      noteReview:
        "{{review}} need review, including unmatched, duplicate and risk-rule-hit entities",
      noteUnmatched:
        "{{unmatched}} unmatched; add business registry info before re-scoring",
    },
    table: {
      title: "Batch evaluation result table",
      countNote: "{{total}} records, {{filtered}} shown",
      searchPlaceholder: "Search company / country / industry",
      riskAll: "All risks",
      statusAll: "All statuses",
      col: {
        rank: "Rank",
        name: "Company",
        country: "Country / region",
        industry: "Industry",
        score: "Score",
        grade: "Grade",
        risk: "Risk",
        pd: "Default prob.",
        limit: "Suggested limit",
        status: "Status",
        profile: "Profile",
      },
      viewProfile: "View company profile",
      emptyTitle: "No records match the current filters",
      emptyDesc: "Try adjusting the risk level, status filter or clearing the search",
    },
    result: {
      note: "The result table covers all {{count}} records (including unmatched and duplicate rows). After exporting to CSV it can be imported into the risk ledger or passed for approval.",
      rescore: "Re-score",
      exportCsv: "Export result table (CSV)",
    },
    status: {
      ok: "Scored",
      review: "Needs review",
      unmatched: "Unmatched",
    },
    upload: {
      title: "Upload company list",
      subtitle:
        "Supports CSV / TXT; the first column should be the company name or registration number",
      loadSample: "Load sample list",
      chooseFile: "Choose file",
      dropTitle: "Drag the list file here, or click to choose a file",
      dropHint:
        "Up to 5,000 entities per run recommended · parsed locally only",
      sampleLabel: "Sample list",
      fileLabel: "Local upload",
      importedAt: "imported {{time}}",
      remove: "Remove list",
      statParsed: "Parsed records",
      statValid: "Matchable entities",
      statInvalid: "Pending onboarding",
      statStatus: "Parse status",
      statDone: "Validated",
      errors: {
        type: "Only CSV / TXT lists are supported; save as CSV and upload again",
        empty: "The file is empty; no company records could be parsed",
        read: "Failed to read the file; please retry or use another file",
      },
    },
    issue: {
      unmatched: "No entity matched in the credit library; add business registry info and re-score",
      ratingTemplate: 'External rating "{{value}}"; manual review required',
      paidRatioTemplate: "Paid-in capital ratio is only {{value}}%",
      highRisk: "Blocked by a high-risk admission rule; manual review advised",
      duplicateTemplate: "Duplicate of row {{index}} in the list; auto de-duplicated",
    },
    outcome: {
      low: "Recommend approval",
      medium: "Conditional approval",
      high: "Do not add new credit",
    },
    runSteps: {
      parseLabel: "Parse list file",
      parseDetail: 'Read "{{file}}" and identify {{count}} company records',
      validateLabel: "Field validation & normalization",
      validateDetail:
        "Clean company names, registration numbers and source fields; normalized {{count}} records",
      matchLabel: "Entity matching against the library",
      matchDetail:
        "Compared against {{total}} entities in the credit library, matched {{valid}}",
      scoreLabel: "Batch scoring & risk grading",
      scoreDetail:
        "Invoke model {{version}} to output credit score, grade and default probability row by row",
      rankLabel: "Ranking & result summary",
      rankDetail:
        "Rank by credit score desc, flag anomalies and duplicates, and build the result table",
    },
  },
};
export default {
  report: {
    title: "Report",
    subtitle:
      "Streams the underwriting report sentence by sentence; hover the citation chips to view evidence cards",
    notFound: {
      shellSubtitle: "No matching company entity",
      title: "This company does not exist, no report to generate",
      desc: "ID “{{id}}” did not match any entity record. Please return to Company Search and pick a target company again.",
      back: "Back to search",
    },
    copyConclusion: "Copy conclusion",
    exportPdf: "Export PDF",
    copyOk: "Key conclusion copied to clipboard",
    copyFail: "Copy failed, please select the body text manually",
    actionRestart: "Regenerate",
    actionPause: "Pause",
    actionResume: "Resume",
    actionSkip: "Skip animation",
    header: {
      reportNo: "Report no.",
      model: "Model",
      generatedAt: "Generated",
      wordCount: "Word count",
      done: "{{total}} sentences · {{ev}} evidence items",
      generating: "Generating sentence {{current}} / {{total}}…",
      paused: "Paused · {{done}} / {{total}} sentences done",
    },
    body: {
      generating: "Simulating report generation from demo evidence…",
      generatingBadge: "Generating",
      done: "Report complete · {{sent}} sentences · {{ev}} evidence items",
      modelAt: "Model {{version}} · generated {{time}}",
    },
    sidebar: {
      progressTitle: "Generation progress",
      progressSub: "{{done}} / {{total}} sentences generated",
      current: "Current section",
      tocTitle: "Contents",
      tocSub: "Click to jump to a section",
      evidenceTitle: "Evidence sources",
      evidenceSub: "{{count}} evidence items cited",
      evidenceNote:
        "The chips at the end of each sentence map to the evidence numbers above. Hover or click a chip to open its evidence card; the “View source” button inside jumps to the original profile, score or graph page.",
    },
    citation: {
      aria: "View {{count}} evidence items",
      source: "Evidence · {{count}} items",
      pinned: "Pinned",
    },
    evidence: {
      confidence: "Confidence {{pct}}%",
      viewSource: "View source",
    },
  },
};

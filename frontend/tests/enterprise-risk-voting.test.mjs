import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";

test("enterprise predictions display saved votes and link to the exact assistant context", async () => {
  const server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    server: { middlewareMode: true, ws: false, watch: null },
    appType: "custom",
  });
  try {
    const { EnterpriseRiskPanel } = await server.ssrLoadModule("/src/pages/company/real/EnterpriseRiskPanel.tsx");
    const render = result => renderToStaticMarkup(createElement(MemoryRouter, null,
      createElement(EnterpriseRiskPanel, {
        data: {
          dataset: { id: "dataset-1" },
          company: { nodeId: "C/001" },
          predictions: [{ modelId: "vote-version", modelName: "多数投票", result }],
        },
        modelId: "vote-version",
        onUpdated() {},
      })));
    const saved = { probability: 2 / 3, scoreKind: "vote_share", predictedLabel: 1 };
    const positive = { algorithm: "gcn", score: 0.7, threshold: 0.5, vote: 1 };
    const tie = { algorithm: "hgt", score: 0.55, threshold: 0.55, vote: 1 };
    const negative = { algorithm: "rgcn", score: 0.45, threshold: 0.62, vote: 0 };
    const html = render({ ...saved, voting: { positiveVotes: 2, requiredVotes: 2, members: [positive, negative, tie] } });
    assert.match(html, /66\.67%.*判为高风险/);
    assert.match(html, /获得 2\/3 张高风险票，至少需 2 张/);
    assert.match(html, />gcn<\/th>.*>0\.7<\/td>.*>0\.5<\/td>.*>高风险票<\/td>/);
    assert.match(html, />rgcn<\/th>.*>0\.45<\/td>.*>0\.62<\/td>.*>未投高风险票<\/td>/);
    assert.match(html, />hgt<\/th>.*>0\.55<\/td>.*>0\.55<\/td>.*>高风险票<\/td>/);
    assert.match(html, /href="\/chat\?riskDataset=dataset-1&amp;riskModel=vote-version&amp;riskCompany=C%2F001"/);

    const below = render({
      ...saved, probability: 1 / 3, predictedLabel: 0,
      voting: { positiveVotes: 1, requiredVotes: 2, members: [positive, negative, { ...tie, score: 0.54, vote: 0 }] },
    });
    assert.match(below, /33\.33%.*未判为高风险/);
    assert.match(below, /获得 1\/3 张高风险票，至少需 2 张/);
    assert.match(render(saved), /重新预测以获取明细/);
    assert.doesNotMatch(render({ probability: 0.42, predictedLabel: 0 }), /成员模型投票明细/);

    const sensitivity = render({
      ...saved,
      voting: { positiveVotes: 2, requiredVotes: 2, members: [positive, negative, tie] },
      votingExplanation: {
        referenceCount: 10,
        features: [{
          feature: "n_charges_outstanding", value: 10, referenceValue: 2,
          positiveVotesAtReference: 1, predictedLabelAtReference: 0,
          members: [
            { algorithm: "gcn", scoreAtReference: 0.4, delta: 0.3, voteAtReference: 0 },
            { algorithm: "rgcn", scoreAtReference: 0.45, delta: 0, voteAtReference: 0 },
            { algorithm: "hgt", scoreAtReference: 0.55, delta: 0, voteAtReference: 1 },
          ],
        }, {
          feature: "age_months", value: 40, referenceValue: 50,
          positiveVotesAtReference: 3, predictedLabelAtReference: 1,
          members: [
            { algorithm: "gcn", scoreAtReference: 0.7, delta: 0, voteAtReference: 1 },
            { algorithm: "rgcn", scoreAtReference: 0.63, delta: -0.18, voteAtReference: 1 },
            { algorithm: "hgt", scoreAtReference: 0.55, delta: 0, voteAtReference: 1 },
          ],
        }, {
          feature: "n_charges", value: 12, referenceValue: 8,
          positiveVotesAtReference: 2, predictedLabelAtReference: 1,
          members: [
            { algorithm: "gcn", scoreAtReference: 0.6, delta: 0.1, voteAtReference: 1 },
            { algorithm: "rgcn", scoreAtReference: 0.45, delta: 0, voteAtReference: 0 },
            { algorithm: "hgt", scoreAtReference: 0.55, delta: 0, voteAtReference: 1 },
          ],
        }],
      },
    });
    assert.match(sensitivity, /未解除抵押数量 · 10 → 2 · 高风险票 2 → 1 · 改判为未达高风险门槛/);
    assert.match(sensitivity, /gcn · 分数 0\.7 → 0\.4 · 变化 -30 个百分点 · 未投高风险票（改票）/);
    assert.match(sensitivity, /高风险票 2 → 3 · 有成员改票，类别不变/);
    assert.match(sensitivity, /高风险票 2 → 2 · 分数变化，投票不变/);
  } finally {
    await server.close();
  }
});

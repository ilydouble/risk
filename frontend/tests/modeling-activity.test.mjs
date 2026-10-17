import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

test("training feedback separates live workers, expired leases and unavailable status", async () => {
  const server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    server: { middlewareMode: true, ws: false, watch: null }, appType: "custom",
  });
  try {
    const { default: i18n } = await server.ssrLoadModule("/src/shared/config/i18n/index.ts");
    await i18n.changeLanguage("zh");
    const { ExperimentActivity } = await server.ssrLoadModule("/src/pages/modeling/components/ExperimentActivity.tsx");
    const run = { status: "running", stage: "preparing", workerAlive: true, epochs: 250,
      heartbeatExpiresAt: new Date(Date.now() + 60_000).toISOString(),
      createdAt: new Date().toISOString() };
    const render = (changes = {}, error = "", checkedAt = Date.now()) => renderToStaticMarkup(
      createElement(ExperimentActivity, { run: { ...run, ...changes }, checkedAt, error }));
    assert.match(render(), /心跳正常/);
    assert.match(render(), /此阶段尚未开始计算训练轮次/);
    assert.match(render({ status: "queued", workerAlive: null }), /等待训练资源/);
    assert.match(render({ heartbeatExpiresAt: new Date(Date.now() - 1000).toISOString() }), /心跳已过期/);
    const disconnected = render({}, "offline");
    assert.match(disconnected, /正在自动重连/);
    assert.doesNotMatch(disconnected, /心跳正常/);
    assert.match(render({}, "", Date.now() - 20_000), /正在自动重连/);
    assert.equal(render({ status: "completed" }), "");
    const { CreateExperimentForm } = await server.ssrLoadModule("/src/pages/modeling/components/CreateExperimentForm.tsx");
    // Configuration loading is asynchronous; the page still needs visible submission feedback.
    const form = renderToStaticMarkup(createElement(CreateExperimentForm, {
      work: { dataset: { id: "dataset", name: "data" }, busy: true, submitting: true },
    }));
    assert.match(form, /正在提交实验/);
  } finally {
    await server.close();
  }
});

import { createServer } from "vite";
import { mkdir, readdir, unlink, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
try {
  const { demoSeedCompanies, demoSeedIds } = await server.ssrLoadModule("/src/features/demo-scenarios/model/fixtures/seedCases.ts");
  if (demoSeedCompanies.length !== demoSeedIds.length) {
    throw new Error("A selected demo company is missing from the frontend fixtures");
  }
  const { resolveProfile } = await server.ssrLoadModule("/src/features/demo-scenarios/lib/profile.ts");
  const { buildScoreDetail } = await server.ssrLoadModule("/src/features/demo-scenarios/lib/score.ts");
  const { buildGraphData } = await server.ssrLoadModule("/src/features/demo-scenarios/lib/graph.ts");
  const records = demoSeedCompanies.map((company) => {
    const profile = resolveProfile(company);
    return {
      company,
      profile,
      scores: {
        zh: buildScoreDetail(company, profile, "zh"),
        en: buildScoreDetail(company, profile, "en"),
      },
      graphs: {
        zh: buildGraphData(demoSeedCompanies, company, profile, "zh"),
        en: buildGraphData(demoSeedCompanies, company, profile, "en"),
      },
    };
  });
  const targetDir = resolve(process.cwd(), "../backend/seed/demo");
  await mkdir(targetDir, { recursive: true });
  const generated = new Set(records.map(({ company }) => `${company.id}.json`));
  for (const filename of await readdir(targetDir)) {
    if (/^C-\d+\.json$/.test(filename) && !generated.has(filename)) {
      await unlink(resolve(targetDir, filename));
    }
  }
  for (const record of records) {
    await writeFile(resolve(targetDir, `${record.company.id}.json`), `${JSON.stringify(record, null, 2)}\n`);
  }
} finally {
  await server.close();
}

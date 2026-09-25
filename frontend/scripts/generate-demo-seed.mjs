import { createServer } from "vite";
import { writeFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
try {
  const { companies } = await server.ssrLoadModule("/src/features/demo-scenarios/model/fixtures/companies.ts");
  const { resolveProfile } = await server.ssrLoadModule("/src/features/demo-scenarios/lib/profile.ts");
  const { buildScoreDetail } = await server.ssrLoadModule("/src/features/demo-scenarios/lib/score.ts");
  const { buildGraphData } = await server.ssrLoadModule("/src/features/demo-scenarios/lib/graph.ts");
  const records = companies.map((company) => {
    const profile = resolveProfile(company);
    return {
      company,
      profile,
      scores: {
        zh: buildScoreDetail(company, profile, "zh"),
        en: buildScoreDetail(company, profile, "en"),
      },
      graphs: {
        zh: buildGraphData(companies, company, profile, "zh"),
        en: buildGraphData(companies, company, profile, "en"),
      },
    };
  });
  const target = resolve(process.cwd(), "../backend/seed/demo.json");
  await mkdir(resolve(process.cwd(), "../backend/seed"), { recursive: true });
  await writeFile(target, `${JSON.stringify(records, null, 2)}\n`);
} finally {
  await server.close();
}

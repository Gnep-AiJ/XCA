import fs from "fs";
import { resolve } from "path";
import { fileURLToPath } from "url";

const { readFile, writeFile } = fs.promises;

const rawUrl = process.argv[2] || process.env.XCA_AGENT_URL || "";

if (!rawUrl) {
  console.error("Usage: npm run configure:extension -- https://your-worker.workers.dev");
  process.exit(1);
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});

async function main() {
  const agentUrl = new URL(rawUrl);
  const origin = agentUrl.origin;
  const hostPermission = `${origin}/*`;
  const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
  const backgroundPath = resolve(root, "extension/background.js");
  const manifestPath = resolve(root, "extension/manifest.json");

  const background = await readFile(backgroundPath, "utf8");
  await writeFile(
    backgroundPath,
    background.replace(
      /const DEFAULT_AGENT_ORIGIN = ".*?";/,
      `const DEFAULT_AGENT_ORIGIN = "${origin}";`
    )
  );

  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  manifest.host_permissions = Array.from(new Set([
    "https://x.com/*",
    "https://twitter.com/*",
    "https://*.workers.dev/*",
    hostPermission
  ]));
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

  console.log(`Extension configured for ${origin}`);
}

import { spawn } from "child_process";

const apiKey = process.env.LLM_API_KEY || "";
const fallbackUrl = process.env.XCA_AGENT_URL || "";

if (!apiKey) {
  console.error("LLM_API_KEY is required. Example: LLM_API_KEY=your-llm-api-key npm run deploy:one");
  process.exit(1);
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});

async function main() {
  await run("npx", ["wrangler", "secret", "put", "LLM_API_KEY"], {
    input: `${apiKey}\n`
  });

  const deployOutput = await run("npx", ["wrangler", "deploy"]);
  const deployedUrl = findWorkerUrl(deployOutput) || fallbackUrl;

  if (!deployedUrl) {
    console.error("Deploy completed, but the Worker URL was not detected.");
    console.error("Run: npm run configure:extension -- https://your-worker.workers.dev");
    process.exit(1);
  }

  await run("node", ["scripts/configure-extension.mjs", deployedUrl]);
  await run("node", ["scripts/package-extension.mjs"]);

  console.log("");
  console.log(`Worker URL: ${deployedUrl}`);
  console.log("Extension package: dist/extension");
}

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: ["pipe", "pipe", "pipe"],
      env: process.env
    });

    let output = "";
    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      output += text;
      process.stdout.write(text);
    });
    child.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      output += text;
      process.stderr.write(text);
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve(output);
      } else {
        reject(new Error(`${command} ${args.join(" ")} exited with ${code}`));
      }
    });

    if (options.input) {
      child.stdin.write(options.input);
    }
    child.stdin.end();
  });
}

function findWorkerUrl(output) {
  const matches = output.match(/https:\/\/[^\s"'<>]+\.workers\.dev/g) || [];
  return matches[matches.length - 1] || "";
}

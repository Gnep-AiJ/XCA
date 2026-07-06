import fs from "fs";
import { resolve } from "path";
import { fileURLToPath } from "url";

const { mkdir } = fs.promises;

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const source = resolve(root, "extension");
const target = resolve(root, "dist/extension");

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});

async function main() {
  removeDirectory(target);
  await mkdir(target, { recursive: true });
  copyDirectory(source, target);

  console.log(`Extension package ready: ${target}`);
}

function removeDirectory(targetPath) {
  if (fs.existsSync(targetPath)) {
    fs.rmdirSync(targetPath, { recursive: true });
  }
}

function copyDirectory(sourcePath, targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
  for (const entry of fs.readdirSync(sourcePath, { withFileTypes: true })) {
    const from = resolve(sourcePath, entry.name);
    const to = resolve(targetPath, entry.name);
    if (entry.isDirectory()) {
      copyDirectory(from, to);
    } else {
      fs.copyFileSync(from, to);
    }
  }
}

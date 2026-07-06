#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKER_NAME="${WORKER_NAME:-xca-agent}"
LLM_BASE_URL="${LLM_BASE_URL:-https://api.deepseek.com}"
LLM_MODEL="${LLM_MODEL:-deepseek-v4-pro}"
DEFAULT_PERSONA="${DEFAULT_PERSONA:-practical operator, curious builder, concise and natural}"

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "$name is required" >&2
    exit 1
  fi
}

require_env CLOUDFLARE_ACCOUNT_ID
require_env CLOUDFLARE_API_TOKEN
require_env LLM_API_KEY
require_env XCA_AGENT_URL

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

python3 - "$TMP_DIR/metadata.json" "$LLM_BASE_URL" "$LLM_MODEL" "$DEFAULT_PERSONA" <<'PY'
import json
import sys

metadata_path, base_url, model, persona = sys.argv[1:5]
metadata = {
    "main_module": "index.js",
    "compatibility_date": "2026-07-06",
    "bindings": [
        {"type": "plain_text", "name": "LLM_BASE_URL", "text": base_url},
        {"type": "plain_text", "name": "LLM_MODEL", "text": model},
        {"type": "plain_text", "name": "DEFAULT_PERSONA", "text": persona},
    ],
}
with open(metadata_path, "w", encoding="utf-8") as file:
    json.dump(metadata, file, separators=(",", ":"))
PY

echo "Verifying Cloudflare token..."
curl --fail --silent --show-error \
  "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/verify" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  >/dev/null

echo "Uploading Worker ${WORKER_NAME}..."
curl --fail --silent --show-error \
  "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/workers/scripts/${WORKER_NAME}" \
  -X PUT \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -F "metadata=@${TMP_DIR}/metadata.json;type=application/json" \
  -F "index.js=@${ROOT_DIR}/worker/src/index.js;type=application/javascript+module" \
  >/dev/null

echo "Writing LLM_API_KEY secret..."
python3 - "$TMP_DIR/secret.json" "$LLM_API_KEY" <<'PY'
import json
import sys

secret_path, api_key = sys.argv[1:3]
with open(secret_path, "w", encoding="utf-8") as file:
    json.dump({"name": "LLM_API_KEY", "text": api_key, "type": "secret_text"}, file)
PY

curl --fail --silent --show-error \
  "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/workers/scripts/${WORKER_NAME}/secrets" \
  -X PUT \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data @"${TMP_DIR}/secret.json" \
  >/dev/null

echo "Configuring extension for ${XCA_AGENT_URL}..."
python3 - "$ROOT_DIR" "$XCA_AGENT_URL" <<'PY'
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

root = Path(sys.argv[1])
raw_url = sys.argv[2]
parsed = urlparse(raw_url)
origin = f"{parsed.scheme}://{parsed.netloc}"
if parsed.scheme != "https" or not parsed.netloc:
    raise SystemExit("XCA_AGENT_URL must be an https URL")

background_path = root / "extension" / "background.js"
manifest_path = root / "extension" / "manifest.json"

background = background_path.read_text(encoding="utf-8")
background = re.sub(
    r'const DEFAULT_AGENT_ORIGIN = ".*?";',
    f'const DEFAULT_AGENT_ORIGIN = "{origin}";',
    background,
)
background_path.write_text(background, encoding="utf-8")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
permissions = [
    "https://x.com/*",
    "https://twitter.com/*",
    "https://*.workers.dev/*",
    f"{origin}/*",
]
manifest["host_permissions"] = list(dict.fromkeys(permissions))
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

dist = root / "dist" / "extension"
if dist.exists():
    shutil.rmtree(dist)
dist.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(root / "extension", dist)
PY

echo "Done."
echo "Worker URL: ${XCA_AGENT_URL}"
echo "Extension package: ${ROOT_DIR}/dist/extension"

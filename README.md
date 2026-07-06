# X Comment Agent Cloudflare

Standalone Cloudflare deployment for the X Comment Agent.

This package is intentionally separated from the development workspace. It
contains only:

- Cloudflare Worker backend
- Chrome extension source
- deployment/configuration scripts

It does not include local Python services, workspace paths, local `.env` files,
or API keys.

## What You Need To Provide

To deploy this for you, I need:

1. Cloudflare account access
   - Either a `CLOUDFLARE_API_TOKEN`, or you can run `npx wrangler login`.
   - Token permissions should allow Workers deploys and Worker secret edits.
2. Worker name
   - Default is `xca-agent`; tell me if you want another name.
3. LLM provider settings
   - `LLM_API_KEY`
   - `LLM_BASE_URL`, default: `https://api.deepseek.com`
   - `LLM_MODEL`, default: `deepseek-v4-pro`
4. Final public Worker URL
   - Usually `https://xca-agent.<your-subdomain>.workers.dev`
   - After deploy, this URL is written into the extension with
     `npm run configure:extension -- https://...`

## One-Command Deploy

Recommended path when Node.js is available:

```bash
cd xca-cloudflare-agent
npm install
export CLOUDFLARE_API_TOKEN="your-cloudflare-token"
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
export LLM_API_KEY="your-llm-api-key"
npm run deploy:one
```

`deploy:one` does four things:

1. Writes `LLM_API_KEY` to Cloudflare Worker Secrets.
2. Deploys the Worker.
3. Writes the deployed Worker URL into the Chrome extension.
4. Builds the loadable extension into `dist/extension`.

If the server does not have Node.js, use the REST API fallback:

```bash
cd xca-cloudflare-agent
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
export CLOUDFLARE_API_TOKEN="your-cloudflare-token"
export LLM_API_KEY="your-llm-api-key"
export XCA_WORKERS_SUBDOMAIN="your-workers-dev-subdomain"
bash scripts/deploy-with-curl.sh
```

The curl path uses Cloudflare's Worker upload API and Worker secret API directly.
It also enables the Worker on workers.dev with Cloudflare's Worker subdomain API.
It does not write credentials into this project.

If you already know the final URL, you can provide it directly:

```bash
export XCA_AGENT_URL="https://your-worker-url.workers.dev"
```

## Deploy

```bash
cd xca-cloudflare-agent
npm install
npx wrangler secret put LLM_API_KEY
npm run deploy
```

After Cloudflare prints the Worker URL:

```bash
npm run configure:extension -- https://xca-agent.<your-subdomain>.workers.dev
npm run package:extension
```

Load the generated extension from:

```text
xca-cloudflare-agent/dist/extension
```

## Chrome Extension

The extension reads only the visible X page content in your browser. It does not
use the X API and does not auto-post. It sends the current post text plus limited
visible thread context to your Cloudflare Worker, then shows copyable draft
replies.

## API

`POST /api/generate`

```json
{
  "tweet": "source post text",
  "context": "optional visible thread context",
  "language": "auto",
  "style": "natural",
  "count": 5,
  "max_chars": 220
}
```

Response:

```json
{
  "candidates": [
    {
      "angle": "question",
      "text": "Draft reply",
      "score": 89,
      "risk": "low"
    }
  ],
  "language": "en",
  "provider": "deepseek:deepseek-v4-pro"
}
```

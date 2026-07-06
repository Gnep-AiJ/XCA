# X Comment Agent

Local-first agent for drafting X replies from the post you are reading.

It does not use the X API, does not automate posting, and does not require
Cloudflare. The Chrome extension reads the visible X page text, sends it to your
local agent server, and returns reply drafts for you to review and copy.

## Features

- Chrome extension for `x.com` and `twitter.com`
- Local web UI for LLM configuration and manual drafting
- Same-language reply generation for Chinese and English posts
- Chinese reading aid for English drafts; copy only copies the English reply
- Context-aware mode using visible thread, timeline text, post time, page URL,
  and image alt text
- Optional `Context note` for charts, screenshots, memes, or background that the
  page does not expose as text
- Custom reply styles in `tools/x_comment_agent/styles.json`
- No X API, no automatic posting, no hosted backend

## Requirements

- Python 3.10+
- Chrome or Chromium-based browser
- An OpenAI-compatible LLM API key

The default config targets DeepSeek:

```text
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
```

You can also use another OpenAI-compatible provider by changing `LLM_BASE_URL`
and `LLM_MODEL`.

## Quick Start

```bash
git clone git@github.com:Gnep-AiJ/XCA.git
cd XCA
cp .env.example .env
```

Edit `.env` and put in your own key:

```text
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_MODEL=deepseek-v4-pro
```

Start the local agent:

```bash
python3 -m tools.x_comment_agent.web --host 0.0.0.0 --port 8765
```

Open the printed URL, usually:

```text
http://127.0.0.1:8765/
```

If the browser is on another machine, open the server LAN IP instead, for
example:

```text
http://192.168.31.188:8765/
```

You can also configure the API key from the web UI with `Configure API Key`.

## Load The Chrome Extension

1. Open `chrome://extensions`.
2. Enable `Developer mode`.
3. Click `Load unpacked`.
4. Select this folder:

```text
tools/x_comment_agent/extension
```

Open an X post and click the floating `AI Reply` button.

## Use

1. Start the local agent server.
2. Open an X post.
3. Click `AI Reply`.
4. Optionally open `Context note` and describe images, charts, screenshots, or
   background.
5. Click `Generate Reply`.
6. Review a draft, copy it, and paste it into X manually.

The tool never posts for you.

## Remote Browser Setup

If Chrome is not running on the same machine as the agent server, update both
files below with your server IP:

```text
tools/x_comment_agent/extension/background.js
tools/x_comment_agent/extension/manifest.json
```

Example endpoint:

```text
http://192.168.31.188:8765/api/generate
```

Then reload the extension in `chrome://extensions`.

## CLI

The project also includes a small local CLI:

```bash
python3 -m tools.x_comment_agent --tweet "AI agents need evals more than demos."
```

Read from stdin:

```bash
echo "Open source agents are becoming distribution channels." | python3 -m tools.x_comment_agent
```

JSON output:

```bash
python3 -m tools.x_comment_agent \
  --tweet "The best open source projects are distribution engines." \
  --format json
```

## Reply Styles

Built-in styles:

- `adaptive`: default context-aware style; chooses witty, thoughtful, technical,
  or skeptical tone based on the post
- `natural`: concise and human
- `sharp`: more opinionated, still respectful
- `supportive`: warm and constructive
- `technical`: implementation, metrics, workflow, and tradeoffs
- `curious`: question-led conversation

Custom styles live here:

```text
tools/x_comment_agent/styles.json
```

Reload the extension after editing styles.

## Safety Boundaries

- No X API
- No auto-posting
- No Cloudflare or hosted backend
- No API key stored in the extension
- `.env`, databases, logs, zip files, and caches are ignored by Git

The LLM key is stored in your local `.env` when configured through the web UI.

## Test

```bash
python3 -m unittest discover tools/x_comment_agent/tests
python3 -m py_compile tools/x_comment_agent/web.py tools/x_comment_agent/llm.py tools/x_comment_agent/agent.py tools/x_comment_agent/styles.py tools/x_comment_agent/cli.py
node --check tools/x_comment_agent/extension/content.js
node --check tools/x_comment_agent/extension/background.js
```

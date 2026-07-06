# X Comment Agent

Local-first assistant for drafting high-signal replies to X posts.

This project deliberately avoids the X API and Cloudflare deployment. It runs on
your own machine or server, reads X page text through the bundled Chrome
extension, drafts replies with your local LLM API configuration, and leaves final
posting to you.

## Quick Start

```bash
git clone git@github.com:Gnep-AiJ/XCA.git
cd XCA
python3 -m tools.x_comment_agent --tweet "Open source agents are becoming the new SaaS distribution layer."
```

Read from stdin:

```bash
echo "AI agents need evals more than demos." | python3 -m tools.x_comment_agent
```

Generate more candidates:

```bash
python3 -m tools.x_comment_agent \
  --tweet "LangGraph is useful because durable execution matters for real agents." \
  --count 8 \
  --persona "technical founder building AI tools"
```

JSON output:

```bash
python3 -m tools.x_comment_agent \
  --tweet "The best open source projects are distribution engines." \
  --format json
```

## Web UI

Run the local web interface:

```bash
cd /path/to/XCA
python3 -m tools.x_comment_agent.web --host 0.0.0.0 --port 8765
```

Open the printed `http://<ip>:8765` URL in your browser.

Configure LLM in either place:

```text
UI: Configure API Key
File: .env
```

`.env` example:

```text
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-v4-pro
```

## Chrome Extension

The extension can read the currently opened X post from the browser page and send
it to the local agent server.

1. Start the web server on port `8765`.
2. Open `chrome://extensions`.
3. Enable `Developer mode`.
4. Click `Load unpacked`.
5. Select:

```text
tools/x_comment_agent/extension
```

Open an X status page and click the floating `XCA` button. The extension reads
the current post, detects the source language, and automatically generates 5
drafts in that same language. It only drafts comments; it does not post to X.
When drafts are in English, the card also shows a Chinese reading aid under the
reply. The copy button only copies the English reply text.

If your browser is not on the same machine as the agent server, make sure
`extension/background.js` contains the server URL, for example:

```text
http://192.168.31.188:8765/api/generate
```

## Design

The current version is intentionally bounded:

- no X API
- no automatic posting
- no Cloudflare deployment
- local LLM API key only
- 5 same-language drafts by default
- Chinese reading aid for English drafts, kept separate from copied text
- configurable reply styles
- local rule fallback if DeepSeek is unavailable

## Reply Styles

Built-in styles:

- `adaptive`: context-aware default; chooses witty, thoughtful, technical, or skeptical tone based on the post and visible context
- `natural`: concise, human, low-drama
- `sharp`: more opinionated, still respectful
- `supportive`: warm and constructive
- `technical`: concrete operator/implementation angle
- `curious`: question-led conversation

Custom styles live in:

```text
tools/x_comment_agent/styles.json
```

Add or edit entries there, then reload the Chrome extension if you want the
style selector to expose a new option.

## Generation

The agent uses DeepSeek first and falls back to a deterministic local rule engine
if the API is unavailable. It detects whether the source post is Chinese or
English and generates replies in that language. The LLM API key is read from
server-side environment variables or the project `.env`; it is never stored in
the Chrome extension.

DeepSeek default:

```text
DEEPSEEK_MODEL=deepseek-v4-pro
```

The server enables high reasoning for `deepseek-v4-pro`. If the model returns
empty or non-JSON content with thinking enabled, the server retries once with the
same model and thinking disabled before falling back to local rules.

When the Chrome extension is used on a reply/comment page, it sends the current
post, visible parent/thread posts, visible timeline text, post time, page URL,
and image alt/aria text as hidden context. The extension cannot truly inspect
image pixels by itself; if an image/chart/screenshot matters, add a short note
in the extension's `Context note` box before generating.

The fallback engine works like this:

1. Clean the source post.
2. Extract a topic, an anchor phrase, a likely tension, and an execution detail.
3. Generate replies from natural conversation angles: add-on, question, soft
   disagreement, operator view, product angle, metric question, or caution.
4. Score candidates by specificity, length, risk, and whether they reference the
   source post directly.
5. Return low-risk drafts for manual review and copying.

Natural reply principle:

```text
Read the source post first, then draft replies that sound like a real person
joining the conversation. Anchor the reply to one concrete phrase or tension in
the post. Prefer one or two short sentences. Avoid slogans, sales language,
generic praise, excessive certainty, and obvious AI summary style.
```

The generated replies use five angles:

- agreement with a specific expansion
- sharp but polite question
- practical operator insight
- soft disagreement
- concise summary or quote-reply style

## Test

```bash
python3 -m unittest discover tools/x_comment_agent/tests
```

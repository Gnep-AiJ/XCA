# X Comment Agent Chrome Extension

Chrome MV3 extension that reads the currently opened X post and sends the text to
the local X Comment Agent web server.

It does not use the X API and does not publish replies. It only drafts comments
for manual review and copying. By default it calls the agent server at
`http://192.168.31.188:8765`, then falls back to `127.0.0.1` and `localhost`.

## Prerequisite

Start the local agent server:

```bash
cd /path/to/XCA
python3 -m tools.x_comment_agent.web --host 0.0.0.0 --port 8765
```

## Load In Chrome

1. Open `chrome://extensions`.
2. Enable `Developer mode`.
3. Click `Load unpacked`.
4. Select this folder:

```text
tools/x_comment_agent/extension
```

## Use

1. Open any `x.com/.../status/...` page while logged in.
2. Click the `AI Reply` floating button on the right side.
3. Optionally open `Context note` and describe images, charts, screenshots, or background that the page does not expose as text.
4. Click `Generate Reply`.
5. Copy a candidate and paste it into X manually.

Use `Open Control Panel` to configure the local LLM API key. The key is saved in
the local agent project's `.env`; it is not stored in the extension.

For English drafts, each card can show a Chinese reading aid. The `Copy` button
copies only the English reply text, not the Chinese translation.

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
from typing import Any

from .agent import (
    CommentAgent,
    CommentRequest,
    DEFAULT_COUNT,
    DEFAULT_MAX_CHARS,
    DEFAULT_PERSONA,
    detect_language,
    resolve_language,
)
from .llm import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL, DeepSeekClient
from .styles import get_style, list_styles, save_styles_config, styles_config


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>X Comment Agent</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f4ee;
      --panel: #fffdf8;
      --panel-strong: #f5efe5;
      --text: #2f2a24;
      --muted: #73675c;
      --line: #ded7cc;
      --primary: #8a5b3d;
      --primary-dark: #744b32;
      --danger: #b42318;
      --shadow: 0 12px 28px rgba(22, 24, 28, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    header {
      background: #fffdf8;
      border-bottom: 1px solid var(--line);
    }
    .topbar {
      max-width: 1180px;
      margin: 0 auto;
      padding: 18px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 720;
      letter-spacing: 0;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--primary);
    }
    main {
      max-width: 1180px;
      width: 100%;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .controls {
      padding: 18px;
      position: sticky;
      top: 16px;
    }
    label {
      display: block;
      color: #4a4036;
      font-size: 13px;
      font-weight: 650;
      margin-bottom: 8px;
    }
    textarea,
    input,
    select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--text);
      background: #fffdf8;
      font: inherit;
      font-size: 14px;
      outline: none;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    textarea {
      min-height: 210px;
      resize: vertical;
      padding: 12px;
    }
    input,
    select {
      height: 40px;
      padding: 0 10px;
    }
    textarea:focus,
    input:focus,
    select:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.14);
    }
    .field { margin-bottom: 16px; }
    .grid2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .segmented {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
      background: var(--panel-strong);
    }
    .segmented button {
      height: 38px;
      border: 0;
      border-right: 1px solid var(--line);
      background: transparent;
      color: #324052;
      font: inherit;
      font-size: 13px;
      cursor: pointer;
    }
    .segmented button:last-child { border-right: 0; }
    .segmented button.active {
      background: var(--primary);
      color: #fff;
      font-weight: 700;
    }
    .actions {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .primary,
    .secondary,
    .copy {
      border: 1px solid transparent;
      border-radius: 6px;
      height: 40px;
      padding: 0 14px;
      font: inherit;
      font-size: 14px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      white-space: nowrap;
    }
    .primary {
      flex: 1;
      background: var(--primary);
      color: #fff;
      font-weight: 720;
    }
    .primary:hover { background: var(--primary-dark); }
    .secondary,
    .copy {
      background: #fff;
      border-color: var(--line);
      color: #4a4036;
    }
    .results {
      min-height: 520px;
      padding: 18px;
    }
    .results-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }
    .results-title {
      margin: 0;
      font-size: 17px;
      font-weight: 720;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
    }
    .list {
      display: grid;
      gap: 10px;
    }
    .candidate {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 13px;
    }
    .candidate-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
    }
    .badges {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      min-width: 0;
    }
    .badge {
      border-radius: 999px;
      background: var(--panel-strong);
      color: #67594e;
      font-size: 12px;
      padding: 4px 8px;
      white-space: nowrap;
    }
    .badge.low { color: #067647; background: #e7f6ef; }
    .badge.medium { color: #92400e; background: #fff3d6; }
    .badge.high { color: var(--danger); background: #fee4e2; }
    .candidate p {
      margin: 0;
      font-size: 15px;
      color: #2f2a24;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }
    .translation {
      margin-top: 8px;
      border-top: 1px solid var(--line);
      padding-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }
    .empty {
      min-height: 420px;
      display: grid;
      place-items: center;
      color: var(--muted);
      text-align: center;
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: #fbf7ef;
      padding: 28px;
    }
    .error {
      color: var(--danger);
      background: #fff1f0;
      border: 1px solid #ffcdc8;
      border-radius: 6px;
      padding: 10px 12px;
      margin-top: 12px;
      display: none;
      font-size: 13px;
    }
    .api-status {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .api-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel-strong);
      color: var(--muted);
      padding: 6px 10px;
      font-size: 13px;
    }
    .api-pill.configured .dot { background: #16a36f; }
    .api-pill.missing .dot { background: #b42318; }
    .dialog {
      position: fixed;
      inset: 0;
      z-index: 50;
      display: none;
      place-items: center;
      background: rgba(47, 42, 36, 0.28);
      padding: 20px;
    }
    .dialog.open { display: grid; }
    .dialog-panel {
      width: min(460px, 100%);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 24px 64px rgba(47, 42, 36, 0.2);
      padding: 18px;
    }
    .dialog-panel h2 {
      margin: 0 0 14px;
      font-size: 17px;
    }
    .dialog-actions {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
      margin-top: 16px;
    }
    @media (max-width: 860px) {
      .topbar {
        align-items: flex-start;
        flex-direction: column;
      }
      main {
        grid-template-columns: 1fr;
        padding: 14px;
      }
      .controls { position: static; }
      .grid2 { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="topbar">
        <h1>X Comment Agent</h1>
        <div class="api-status">
          <span class="api-pill" id="apiPill"><span class="dot"></span><span id="apiStatusText">Checking LLM API...</span></span>
          <button class="secondary" id="configureApi" type="button">Configure API Key</button>
        </div>
      </div>
    </header>
    <main>
      <section class="panel controls" aria-label="Input controls">
        <div class="field">
          <label for="tweet">大 V 推文 / Source post</label>
          <textarea id="tweet" placeholder="Paste the X post text here..."></textarea>
        </div>
        <div class="field">
          <label>Language</label>
          <div class="segmented" id="languageTabs">
            <button type="button" data-language="auto" class="active">Auto</button>
            <button type="button" data-language="zh">中文</button>
            <button type="button" data-language="en">English</button>
          </div>
        </div>
        <div class="field">
          <label for="styleSelect">Reply style</label>
          <select id="styleSelect"></select>
        </div>
        <div class="actions">
          <button class="primary" id="generate" type="button">Generate</button>
          <button class="secondary" id="clear" type="button">Clear</button>
        </div>
        <div class="error" id="error"></div>
      </section>
      <section class="panel results" aria-label="Generated replies">
        <div class="results-head">
          <h2 class="results-title">Candidates</h2>
          <span class="meta" id="summary">Ready</span>
        </div>
        <div id="list" class="list">
          <div class="empty">Paste a post and generate reply candidates.</div>
        </div>
      </section>
    </main>
    <div class="dialog" id="apiDialog" role="dialog" aria-modal="true" aria-label="Configure LLM API">
      <div class="dialog-panel">
        <h2>Configure LLM API</h2>
        <div class="field">
          <label for="apiBaseUrlInput">Base URL</label>
          <input id="apiBaseUrlInput" list="baseUrlOptions" placeholder="https://api.deepseek.com">
          <datalist id="baseUrlOptions">
            <option value="https://api.deepseek.com"></option>
            <option value="https://api.openai.com/v1"></option>
            <option value="http://localhost:11434/v1"></option>
          </datalist>
        </div>
        <div class="field">
          <label for="apiKeyInput">API Key</label>
          <input id="apiKeyInput" type="password" placeholder="sk-...">
        </div>
        <div class="field">
          <label for="apiModelInput">Model</label>
          <input id="apiModelInput" list="modelOptions" value="deepseek-v4-pro">
          <datalist id="modelOptions">
            <option value="deepseek-v4-pro"></option>
            <option value="deepseek-v4-flash"></option>
            <option value="gpt-4.1"></option>
            <option value="gpt-4.1-mini"></option>
            <option value="qwen3-coder-plus"></option>
          </datalist>
        </div>
        <div class="dialog-actions">
          <button class="secondary" id="cancelApi" type="button">Cancel</button>
          <button class="primary" id="saveApi" type="button">Save API Key</button>
        </div>
      </div>
    </div>
  </div>
  <script>
    const DEFAULT_PERSONA = "practical operator, curious builder, concise and natural";
    const DEFAULT_COUNT = 5;
    const DEFAULT_MAX_CHARS = 220;
    const state = { language: "auto" };
    const tweet = document.getElementById("tweet");
    const styleSelect = document.getElementById("styleSelect");
    const list = document.getElementById("list");
    const error = document.getElementById("error");
    const summary = document.getElementById("summary");
    const generate = document.getElementById("generate");
    const apiDialog = document.getElementById("apiDialog");
    const apiPill = document.getElementById("apiPill");
    const apiStatusText = document.getElementById("apiStatusText");
    const apiBaseUrlInput = document.getElementById("apiBaseUrlInput");
    const apiKeyInput = document.getElementById("apiKeyInput");
    const apiModelInput = document.getElementById("apiModelInput");

    loadStyles();
    loadApiStatus();

    document.getElementById("configureApi").addEventListener("click", () => {
      apiDialog.classList.add("open");
      apiKeyInput.value = "";
      apiKeyInput.focus();
    });
    document.getElementById("cancelApi").addEventListener("click", () => {
      apiDialog.classList.remove("open");
    });
    document.getElementById("saveApi").addEventListener("click", saveApiKey);

    document.querySelectorAll("#languageTabs button").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll("#languageTabs button").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        state.language = button.dataset.language;
      });
    });

    document.getElementById("clear").addEventListener("click", () => {
      tweet.value = "";
      list.innerHTML = '<div class="empty">Paste a post and generate reply candidates.</div>';
      summary.textContent = "Ready";
      hideError();
      tweet.focus();
    });

    generate.addEventListener("click", async () => {
      hideError();
      const source = tweet.value.trim();
      if (!source) {
        showError("Paste a source post first.");
        return;
      }
      generate.disabled = true;
      generate.textContent = "Generating";
      summary.textContent = "Working";
      try {
        const response = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tweet: source,
            persona: DEFAULT_PERSONA,
            count: DEFAULT_COUNT,
            max_chars: DEFAULT_MAX_CHARS,
            language: state.language,
            style: styleSelect.value || "adaptive",
            use_llm: true
          })
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "Generation failed.");
        }
        render(payload.candidates || []);
        summary.textContent = `${payload.candidates.length} generated`;
      } catch (err) {
        showError(err.message || "Generation failed.");
        summary.textContent = "Failed";
      } finally {
        generate.disabled = false;
        generate.textContent = "Generate";
      }
    });

    function render(candidates) {
      if (!candidates.length) {
        list.innerHTML = '<div class="empty">No candidates generated.</div>';
        return;
      }
      list.innerHTML = "";
      for (const candidate of candidates) {
        const item = document.createElement("article");
        item.className = "candidate";

        const top = document.createElement("div");
        top.className = "candidate-top";

        const badges = document.createElement("div");
        badges.className = "badges";
        badges.appendChild(badge(candidate.language || "draft"));
        badges.appendChild(badge(candidate.angle || "angle"));
        badges.appendChild(badge(`score ${candidate.score}`));
        badges.appendChild(badge(candidate.risk || "low", candidate.risk || "low"));

        const copy = document.createElement("button");
        copy.className = "copy";
        copy.type = "button";
        copy.textContent = "Copy";
        copy.addEventListener("click", async () => {
          await navigator.clipboard.writeText(candidate.text);
          copy.textContent = "Copied";
          setTimeout(() => { copy.textContent = "Copy"; }, 1200);
        });

        const text = document.createElement("p");
        text.textContent = candidate.text;

        top.appendChild(badges);
        top.appendChild(copy);
        item.appendChild(top);
        item.appendChild(text);
        if (candidate.translation) {
          const translation = document.createElement("div");
          translation.className = "translation";
          translation.textContent = `中文释义：${candidate.translation}`;
          item.appendChild(translation);
        }
        list.appendChild(item);
      }
    }

    function badge(text, level) {
      const node = document.createElement("span");
      node.className = `badge ${level || ""}`;
      node.textContent = text;
      return node;
    }

    function showError(message) {
      error.textContent = message;
      error.style.display = "block";
    }

    function hideError() {
      error.textContent = "";
      error.style.display = "none";
    }

    async function loadStyles() {
      const response = await fetch("/api/styles");
      const payload = await response.json();
      if (!response.ok) {
        showError(payload.error || "Could not load styles.");
        return;
      }
      styleSelect.innerHTML = "";
      for (const style of payload.styles || []) {
        const option = document.createElement("option");
        option.value = style.key;
        option.textContent = style.label;
        styleSelect.appendChild(option);
      }
      styleSelect.value = "adaptive";
    }

    async function loadApiStatus() {
      const response = await fetch("/api/key/status");
      const payload = await response.json();
      if (!response.ok) {
        apiStatusText.textContent = "LLM API status unavailable";
        apiPill.className = "api-pill missing";
        return;
      }
      apiPill.className = `api-pill ${payload.configured ? "configured" : "missing"}`;
      apiStatusText.textContent = payload.configured ? "Local LLM API connected" : "Local LLM API key required";
      apiBaseUrlInput.value = payload.base_url || "https://api.deepseek.com";
      apiModelInput.value = payload.model || "deepseek-v4-pro";
    }

    async function saveApiKey() {
      hideError();
      const apiKey = apiKeyInput.value.trim();
      const baseUrl = apiBaseUrlInput.value.trim() || "https://api.deepseek.com";
      const model = apiModelInput.value.trim() || "deepseek-v4-pro";
      if (!apiKey) {
        showError("API key is required.");
        return;
      }
      const response = await fetch("/api/key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, base_url: baseUrl, model })
      });
      const payload = await response.json();
      if (!response.ok) {
        showError(payload.error || "Could not save API key.");
        return;
      }
      apiDialog.classList.remove("open");
      await loadApiStatus();
      summary.textContent = "API key saved";
    }
  </script>
</body>
</html>
"""


class XCommentHandler(BaseHTTPRequestHandler):
    server_version = "XCommentAgent/0.1"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send_html(HTML)
            return
        if self.path == "/health":
            self._send_json({"ok": True})
            return
        if self.path == "/api/styles":
            self._send_json({"styles": list_styles()})
            return
        if self.path == "/api/styles/config":
            self._send_json(styles_config())
            return
        if self.path == "/api/key/status":
            self._send_json(api_key_status())
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:
        if self.path in ("/", "/index.html", "/health"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8" if self.path != "/health" else "application/json")
            self._send_cors_headers()
            self.end_headers()
            return
        self.send_response(HTTPStatus.NOT_FOUND)
        self._send_cors_headers()
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/api/key":
            try:
                payload = self._read_json()
                status = save_api_key(payload)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(status)
            return

        if self.path == "/api/styles/config":
            try:
                payload = self._read_json()
                config = save_styles_config(payload.get("styles"))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(config)
            return

        if self.path != "/api/generate":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            candidates, meta = generate_candidates_with_meta(payload)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"candidates": candidates, **meta})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("request body is required")
        if content_length > 65536:
            raise ValueError("request body is too large")
        raw = self.rfile.read(content_length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON object is required")
        return payload

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def generate_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates, _meta = generate_candidates_with_meta(payload)
    return candidates


def generate_candidates_with_meta(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tweet = str(payload.get("tweet", "")).strip()
    if not tweet:
        raise ValueError("tweet text is required")
    context = str(payload.get("context", "")).strip()
    timeline_context = str(payload.get("timeline_context", "")).strip()
    image_context = str(payload.get("image_context", "")).strip()
    post_time = str(payload.get("post_time", "")).strip()
    page_url = str(payload.get("page_url", "")).strip()
    persona = str(payload.get("persona", "")).strip() or DEFAULT_PERSONA
    count = _bounded_int(payload.get("count", 5), minimum=1, maximum=12)
    max_chars = _bounded_int(payload.get("max_chars", DEFAULT_MAX_CHARS), minimum=80, maximum=500)
    language = str(payload.get("language", "auto")).lower()
    if language not in {"auto", "zh", "en", "both"}:
        raise ValueError("language must be auto, zh, en, or both")
    target_language = resolve_language(tweet, language)
    style = get_style(str(payload.get("style", "natural")))
    use_llm = _truthy(payload.get("use_llm", True))

    request = CommentRequest(
        tweet=tweet,
        persona=persona,
        count=count,
        max_chars=max_chars,
        language=target_language,
        context=context,
        timeline_context=timeline_context,
        image_context=image_context,
        post_time=post_time,
        page_url=page_url,
    )

    if use_llm:
        llm = DeepSeekClient()
        if not llm.enabled:
            raise ValueError("configure your local LLM API key first")
        try:
            llm_result = llm.generate_replies(request, target_language, style)
            return [
                {**candidate.to_dict(), "language": language_label(target_language), "style": style.key}
                for candidate in llm_result.candidates
            ], {"provider": llm_result.provider, "language": target_language, "style": style.key}
        except Exception as exc:
            candidates = generate_rule_replies(request, target_language, style.key)
            return candidates, {
                "provider": "rules:fallback",
                "warning": str(exc),
                "language": target_language,
                "style": style.key,
            }

    return generate_rule_replies(request, target_language, style.key), {
        "provider": "rules",
        "language": target_language,
        "style": style.key,
    }


def generate_rule_replies(request: CommentRequest, target_language: str, style_key: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    agent = CommentAgent()
    rule_request = CommentRequest(**{**request.__dict__, "language": target_language})
    for candidate in agent.generate(rule_request):
        item = candidate.to_dict()
        item["language"] = language_label(target_language)
        item["style"] = style_key
        result.append(item)
    return result


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = ThreadingHTTPServer((host, port), XCommentHandler)
    print(f"X Comment Agent listening on http://{_display_host(host)}:{port}", flush=True)
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the X Comment Agent web UI.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    run(args.host, args.port)
    return 0


def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("numeric option is invalid") from exc
    return max(minimum, min(maximum, number))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def language_label(language: str) -> str:
    return "中文" if language == "zh" else "English"


def api_key_status() -> dict[str, Any]:
    values = read_env_values()
    api_key = (
        os.environ.get("LLM_API_KEY", "").strip()
        or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        or values.get("LLM_API_KEY", "").strip()
        or values.get("DEEPSEEK_API_KEY", "").strip()
    )
    base_url = os.environ.get("LLM_BASE_URL", "").strip() or values.get("LLM_BASE_URL", "").strip() or DEFAULT_LLM_BASE_URL
    model = (
        os.environ.get("LLM_MODEL", "").strip()
        or os.environ.get("DEEPSEEK_MODEL", "").strip()
        or values.get("LLM_MODEL", "").strip()
        or values.get("DEEPSEEK_MODEL", "").strip()
        or DEFAULT_LLM_MODEL
    )
    return {
        "configured": bool(api_key),
        "base_url": base_url,
        "model": model,
        "masked_key": "configured" if api_key else "",
    }


def save_api_key(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = str(payload.get("api_key", "")).strip()
    base_url = str(payload.get("base_url", "")).strip() or DEFAULT_LLM_BASE_URL
    model = str(payload.get("model", "")).strip() or DEFAULT_LLM_MODEL
    if not api_key:
        raise ValueError("api_key is required")
    if not api_key.startswith("sk-"):
        raise ValueError("API key should start with sk-")
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("base_url must start with http:// or https://")
    if not model:
        raise ValueError("model is required")

    values = read_env_values()
    values["LLM_API_KEY"] = api_key
    values["LLM_BASE_URL"] = base_url
    values["LLM_MODEL"] = model
    values["DEEPSEEK_API_KEY"] = api_key
    values["DEEPSEEK_MODEL"] = model
    write_env_values(values)
    os.environ["LLM_API_KEY"] = api_key
    os.environ["LLM_BASE_URL"] = base_url
    os.environ["LLM_MODEL"] = model
    os.environ["DEEPSEEK_API_KEY"] = api_key
    os.environ["DEEPSEEK_MODEL"] = model
    return api_key_status()


def read_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env_values(values: dict[str, str]) -> None:
    existing_order: list[str] = []
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key and key not in existing_order:
                    existing_order.append(key)
    for key in values:
        if key not in existing_order:
            existing_order.append(key)
    ENV_PATH.write_text(
        "".join(f"{key}={values[key]}\n" for key in existing_order if key in values),
        encoding="utf-8",
    )


def mask_key(api_key: str) -> str:
    if len(api_key) <= 10:
        return "configured"
    return f"{api_key[:5]}...{api_key[-4:]}"


def _display_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    return host


if __name__ == "__main__":
    raise SystemExit(main())

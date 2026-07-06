import { EXTENSION_ZIP_HEX } from "./extension-zip.js";
import { LOCAL_UI_HTML } from "./local-ui.js";

const DEFAULT_LLM_BASE_URL = "https://api.deepseek.com";
const DEFAULT_LLM_MODEL = "deepseek-v4-pro";
const DEFAULT_PERSONA = "practical operator, curious builder, concise and natural";
const DEFAULT_COUNT = 5;
const DEFAULT_MAX_CHARS = 220;
const EXTENSION_VERSION = "0.1.0";

const STYLE_PRESETS = {
  natural: {
    label: "Natural",
    prompt:
      "Natural, concise, human. Light opinion, no performance, no sales tone."
  },
  sharp: {
    label: "Sharp",
    prompt:
      "Sharper and more opinionated, but still respectful. Prefer clear judgment over vague agreement."
  },
  supportive: {
    label: "Supportive",
    prompt:
      "Supportive and warm. Add one useful observation without sounding flattering or generic."
  },
  technical: {
    label: "Technical",
    prompt:
      "Concrete implementation angle. Prefer architecture, workflow, reliability, cost, or product constraints."
  },
  curious: {
    label: "Curious",
    prompt:
      "Question-led and thoughtful. Invite conversation without sounding generic or performative."
  },
  founder: {
    label: "Founder",
    prompt:
      "Founder/operator style. Practical, direct, focused on distribution, customer behavior, speed, and tradeoffs."
  },
  web3: {
    label: "Web3",
    prompt:
      "Web3 native but not hype-driven. Mention incentives, community, liquidity, trust, or distribution only when relevant."
  }
};

const SYSTEM_PROMPT = `
You are a senior social media operator helping draft X replies.

Read the source post first, then draft replies that sound like a real person
joining the conversation. Anchor the reply to one concrete phrase or tension in
the post. Prefer one or two short sentences. Avoid slogans, sales language,
generic praise, excessive certainty, and obvious AI summary style.

Output exactly valid JSON. No markdown. No extra text.
Return one object with a "replies" array. Each item has:
- angle: short label
- text: natural reply

Rules:
- Generate exactly 5 replies.
- Write only in the target language.
- Each reply should be 1-2 short sentences.
- Sound like a real person replying under the post, not an article summary.
- Anchor every reply to a concrete idea from the source post.
- If thread context is provided, use it only to understand what the source post is replying to. Reply to the source post itself.
- Mix angles: add-on, question, soft disagreement, operator view, product/metric angle.
- No hashtags, no links, no @mentions, no "follow me", no sales pitch.
- Do not claim private facts or make unverifiable promises.
`.trim();

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders() });
    }

    const url = new URL(request.url);

    try {
      if (request.method === "GET" && url.pathname === "/") {
        return htmlResponse(renderConsoleHtml(url.origin));
      }
      if (request.method === "GET" && url.pathname === "/extension") {
        return htmlResponse(renderExtensionHtml(url.origin));
      }
      if ((request.method === "GET" || request.method === "HEAD") && url.pathname === "/extension/xca-extension.zip") {
        return extensionZipResponse(request.method === "HEAD");
      }
      if (request.method === "GET" && url.pathname === "/api/extension/info") {
        return jsonResponse(extensionInfo(url.origin));
      }
      if (request.method === "GET" && url.pathname === "/health") {
        return jsonResponse({ ok: true, service: "xca-cloudflare-agent" });
      }
      if (request.method === "GET" && url.pathname === "/api/key/status") {
        return jsonResponse({
          configured: Boolean(getApiKey(env)),
          base_url: getBaseUrl(env),
          model: getModel(env)
        });
      }
      if (request.method === "GET" && url.pathname === "/api/styles") {
        return jsonResponse({ styles: Object.entries(STYLE_PRESETS).map(([key, value]) => ({ key, ...value })) });
      }
      if (request.method === "POST" && url.pathname === "/api/generate") {
        return jsonResponse(await generateReplies(request, env));
      }
      if (request.method === "POST" && url.pathname === "/api/key") {
        return jsonResponse({
          configured: Boolean(getApiKey(env)),
          base_url: getBaseUrl(env),
          model: getModel(env),
          message: "Cloudflare deployment uses Worker Secrets for LLM API configuration."
        });
      }

      return jsonResponse({ error: "Not found" }, 404);
    } catch (error) {
      return jsonResponse({ error: error.message || String(error) }, 500);
    }
  }
};

async function generateReplies(request, env) {
  const payload = await request.json();
  const tweet = normalizeText(payload.tweet || "");
  if (!tweet) {
    throw new Error("tweet text is required");
  }

  const language = resolveLanguage(tweet, payload.language || "auto");
  const count = clampNumber(payload.count, DEFAULT_COUNT, 1, 5);
  const maxChars = clampNumber(payload.max_chars, DEFAULT_MAX_CHARS, 60, 400);
  const style = STYLE_PRESETS[payload.style] || STYLE_PRESETS.natural;
  const apiKey = getApiKey(env);

  if (!apiKey) {
    return {
      candidates: fallbackReplies(tweet, language, count, maxChars),
      language,
      provider: "fallback",
      warning: "LLM_API_KEY is not configured"
    };
  }

  const llmPayload = buildLlmPayload({
    tweet,
    context: normalizeText(payload.context || ""),
    persona: payload.persona || env.DEFAULT_PERSONA || DEFAULT_PERSONA,
    language,
    style,
    maxChars,
    model: getModel(env),
    baseUrl: getBaseUrl(env)
  });

  const replies = await callLlm(llmPayload, env, true);
  const candidates = replies.slice(0, 5).map((item, index) => {
    const text = cleanReply(item.text || item.reply || item.comment || "");
    return {
      angle: String(item.angle || `reply ${index + 1}`).trim(),
      text: text.slice(0, maxChars),
      score: 90 - index,
      risk: riskLevel(text)
    };
  }).filter((item) => item.text);

  if (candidates.length !== 5) {
    throw new Error("LLM returned an unexpected candidate count");
  }

  return {
    candidates,
    language,
    provider: `${providerName(getBaseUrl(env))}:${getModel(env)}`
  };
}

function buildLlmPayload({ tweet, context, persona, language, style, maxChars, model, baseUrl }) {
  const llmPayload = {
    model,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      {
        role: "user",
        content: JSON.stringify({
          source_post: tweet,
          thread_context: context,
          persona,
          reply_style: style,
          target_language: language === "zh" ? "Chinese" : "English",
          count: 5,
          max_chars: maxChars
        })
      }
    ],
    temperature: 0.85,
    top_p: 0.9,
    max_tokens: 1200,
    stream: false,
    response_format: { type: "json_object" }
  };

  if (baseUrl.includes("api.deepseek.com") && model === "deepseek-v4-pro") {
    llmPayload.thinking = { type: "enabled" };
    llmPayload.reasoning_effort = "high";
  }

  return llmPayload;
}

async function callLlm(payload, env, allowRetry) {
  const response = await fetch(`${getBaseUrl(env).replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${getApiKey(env)}`
    },
    body: JSON.stringify(payload)
  });

  const raw = await response.text();
  if (!response.ok) {
    throw new Error(`LLM HTTP ${response.status}: ${raw.slice(0, 240)}`);
  }

  const data = JSON.parse(raw);
  const content =
    data &&
    data.choices &&
    data.choices[0] &&
    data.choices[0].message &&
    data.choices[0].message.content
      ? data.choices[0].message.content
      : "";
  if (!content.trim()) {
    if (allowRetry && payload.thinking) {
      const retryPayload = { ...payload };
      delete retryPayload.thinking;
      delete retryPayload.reasoning_effort;
      return callLlm(retryPayload, env, false);
    }
    throw new Error("LLM returned empty content");
  }

  try {
    return parseReplies(content);
  } catch (error) {
    if (allowRetry && payload.thinking) {
      const retryPayload = { ...payload };
      delete retryPayload.thinking;
      delete retryPayload.reasoning_effort;
      return callLlm(retryPayload, env, false);
    }
    throw error;
  }
}

function parseReplies(content) {
  const cleaned = content.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  const data = JSON.parse(cleaned);
  const replies = Array.isArray(data) ? data : data.replies || data.comments || data.candidates || [];
  if (!Array.isArray(replies)) {
    throw new Error("LLM JSON does not contain a replies array");
  }
  return replies.filter((item) => item && typeof item === "object");
}

function fallbackReplies(tweet, language, count, maxChars) {
  const topic = pickTopic(tweet);
  const zh = [
    `这个点值得继续看，尤其是它最后能不能变成真实的日常动作。`,
    `我也在想，真正的瓶颈可能不是概念，而是用户会不会反复回来。`,
    `方向我认同，但还是要看反馈闭环够不够短。`,
    `如果只看一个指标，我会更关心留存，而不是第一波热度。`,
    `${topic}最后拼的可能不是叙事，而是谁能把体验做得足够顺。`
  ];
  const en = [
    "That point is worth watching, especially whether it turns into a repeated daily behavior.",
    "I wonder if the real bottleneck is less the idea and more whether people keep coming back.",
    "I agree with the direction, but the feedback loop still has to get much tighter.",
    "If I had to pick one proof point, I would probably look at retention over first-wave attention.",
    `The hard part for ${topic} is not the narrative. It is making the experience smooth enough to change behavior.`
  ];
  return (language === "zh" ? zh : en).slice(0, count).map((text, index) => ({
    angle: ["add-on", "question", "operator view", "metric", "product angle"][index] || "reply",
    text: text.slice(0, maxChars),
    score: 70 - index,
    risk: riskLevel(text)
  }));
}

function normalizeText(text) {
  return String(text || "").replace(/https?:\/\/\S+/g, "").replace(/\s+/g, " ").trim();
}

function resolveLanguage(text, requested) {
  const language = String(requested || "auto").toLowerCase();
  if (language === "zh" || language === "en") {
    return language;
  }
  const cjkCount = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const latinCount = (text.match(/[A-Za-z]/g) || []).length;
  return cjkCount >= Math.max(4, Math.floor(latinCount / 3)) ? "zh" : "en";
}

function pickTopic(text) {
  if (/github|open source|开源/i.test(text)) return "open source";
  if (/agent|ai|llm|模型|智能体/i.test(text)) return "AI agents";
  if (/web3|crypto|token|链上/i.test(text)) return "Web3";
  return "this";
}

function cleanReply(text) {
  return String(text || "").replace(/\s+/g, " ").replace(/^[-*\d.、\s]+/, "").trim();
}

function riskLevel(text) {
  const lowered = String(text || "").toLowerCase();
  if (/稳赚|百分百|100%|guaranteed|follow me|dm me|私信我|关注我/.test(lowered)) {
    return "high";
  }
  if (/[!?！？]{2,}/.test(text) || text.length > 260) {
    return "medium";
  }
  return "low";
}

function clampNumber(value, fallback, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.max(min, Math.min(max, Math.trunc(number)));
}

function getApiKey(env) {
  return env.LLM_API_KEY || "";
}

function getBaseUrl(env) {
  return env.LLM_BASE_URL || DEFAULT_LLM_BASE_URL;
}

function getModel(env) {
  return env.LLM_MODEL || DEFAULT_LLM_MODEL;
}

function providerName(baseUrl) {
  return baseUrl.includes("api.deepseek.com") ? "deepseek" : "openai-compatible";
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders()
    }
  });
}

function htmlResponse(html) {
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      ...corsHeaders()
    }
  });
}

function extensionZipResponse(headOnly = false) {
  return new Response(headOnly ? null : hexToBytes(EXTENSION_ZIP_HEX), {
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": 'attachment; filename="xca-extension.zip"',
      "Content-Length": String(EXTENSION_ZIP_HEX.length / 2),
      "Cache-Control": "no-store"
    }
  });
}

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = parseInt(hex.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization"
  };
}

function extensionInfo(origin) {
  return {
    name: "X Comment Agent",
    version: EXTENSION_VERSION,
    worker_origin: origin,
    control_panel_url: `${origin}/`,
    download_url: `${origin}/extension/xca-extension.zip`,
    update_check_url: `${origin}/api/extension/info`,
    generate_url: `${origin}/api/generate`
  };
}

function renderConsoleHtml(origin) {
  return withExtensionInstall(LOCAL_UI_HTML, origin);
}

function withExtensionInstall(html, origin) {
  const installButton = '<a class="secondary" href="/extension" style="text-decoration:none">Install Extension</a>';
  if (html.includes(installButton)) {
    return html;
  }
  return html.replace(
    '<button class="secondary" id="configureApi" type="button">Configure API Key</button>',
    `${installButton}\\n          <button class="secondary" id="configureApi" type="button">Configure API Key</button>`
  ).replace(
    "</style>",
    "    a.secondary { text-decoration: none; }\\n  </style>"
  ).replace(
    "</body>",
    `<script>window.XCA_WORKER_ORIGIN = ${JSON.stringify(origin)};</script>\\n</body>`
  );
}

function renderPreviousConsoleHtml(origin) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>X Comment Agent</title>
  <style>
    * { box-sizing: border-box; letter-spacing: 0; }
    body { margin: 0; background: #f6f4ee; color: #26231f; font: 14px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 1120px; margin: 0 auto; padding: 24px 18px 42px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
    h1 { margin: 0; font-size: 24px; font-weight: 760; }
    .sub { margin: 5px 0 0; color: #6c6258; line-height: 1.45; }
    .top-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .layout { display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(320px, .92fr); gap: 16px; align-items: start; }
    .panel { border: 1px solid #ded7cc; border-radius: 8px; background: #fffdf8; box-shadow: 0 16px 46px rgba(49, 40, 31, 0.08); }
    .panel-head { padding: 14px 16px; border-bottom: 1px solid #ebe3d8; display: flex; justify-content: space-between; gap: 12px; align-items: center; }
    .panel-title { margin: 0; font-size: 15px; font-weight: 760; }
    .panel-body { padding: 16px; }
    label { display: block; margin: 0 0 7px; color: #5f564d; font-size: 12px; font-weight: 700; }
    textarea, select, input { width: 100%; border: 1px solid #ded7cc; border-radius: 7px; background: #fffdf8; color: #28231f; font: 14px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; outline: none; }
    textarea { min-height: 210px; padding: 11px; resize: vertical; line-height: 1.5; }
    select, input { height: 38px; padding: 0 10px; }
    textarea:focus, select:focus, input:focus { border-color: #8a5b3d; box-shadow: 0 0 0 3px rgba(138, 91, 61, .14); }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
    button, .button { min-height: 38px; border: 1px solid #ded7cc; border-radius: 7px; background: #fffdf8; color: #413a34; padding: 0 13px; font: 700 13px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }
    button.primary, .button.primary { border-color: #8a5b3d; background: #8a5b3d; color: #fffaf2; }
    button:hover:not(:disabled), .button:hover { background: #f3eee6; }
    button.primary:hover:not(:disabled), .button.primary:hover { background: #744b32; }
    button:disabled { opacity: .62; cursor: default; }
    .status { min-height: 18px; color: #6c6258; font-size: 12px; margin-top: 10px; }
    .status.error { color: #b42318; }
    .pill { border-radius: 999px; background: #e9f7ef; color: #067647; padding: 4px 9px; font-size: 12px; font-weight: 760; white-space: nowrap; }
    .list { display: grid; gap: 10px; }
    .card { border: 1px solid #e7dfd3; border-radius: 8px; background: #fffdf8; padding: 12px; }
    .card-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
    .angle { border-radius: 999px; background: #f3eee6; color: #67594e; padding: 3px 8px; font-size: 11px; font-weight: 700; }
    .reply { margin: 0; color: #28231f; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
    .empty { color: #766b60; line-height: 1.55; margin: 0; }
    .meta { display: grid; gap: 8px; }
    .meta-row { display: flex; justify-content: space-between; gap: 12px; padding: 9px 0; border-top: 1px solid #eee6da; }
    .meta-row:first-child { border-top: 0; }
    code { background: #f3eee6; border-radius: 5px; padding: 2px 5px; overflow-wrap: anywhere; }
    .ok { color: #067647; font-weight: 760; }
    .bad { color: #b42318; font-weight: 760; }
    @media (max-width: 820px) {
      header { align-items: flex-start; flex-direction: column; }
      .layout { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      .top-actions { width: 100%; }
      .button, button { flex: 1; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>X Comment Agent</h1>
        <p class="sub">Generate human-reviewed X reply drafts from the current post text.</p>
      </div>
      <div class="top-actions">
        <a class="button" href="/extension">Install extension</a>
        <a class="button" href="/api/extension/info">Extension info</a>
      </div>
    </header>
    <div class="layout">
      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Generate Replies</h2>
          <span class="pill" id="llm">Checking</span>
        </div>
        <div class="panel-body">
          <label for="tweet">Source post</label>
          <textarea id="tweet" placeholder="Paste an X post here..."></textarea>
          <div class="grid">
            <div>
              <label for="style">Style</label>
              <select id="style">
                <option value="natural">Natural</option>
                <option value="founder">Founder</option>
                <option value="web3">Web3</option>
                <option value="technical">Technical</option>
                <option value="curious">Curious</option>
              </select>
            </div>
            <div>
              <label for="language">Language</label>
              <select id="language">
                <option value="auto">Match source language</option>
                <option value="zh">Chinese</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>
          <div class="actions">
            <button class="primary" id="generate" type="button">Generate 5 Replies</button>
            <button id="clear" type="button">Clear</button>
          </div>
          <div class="status" id="status"></div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Replies</h2>
          <span class="pill" id="provider">Ready</span>
        </div>
        <div class="panel-body">
          <div class="list" id="replies">
            <p class="empty">Generated replies will appear here. Use Copy to paste one into X manually.</p>
          </div>
        </div>
      </section>
    </div>
    <section class="panel" style="margin-top:16px">
      <div class="panel-body meta">
        <div class="meta-row"><strong>Worker</strong><code>${escapeHtml(origin)}</code></div>
        <div class="meta-row"><strong>Generate API</strong><code>POST /api/generate</code></div>
        <div class="meta-row"><strong>Posting</strong><span>No X API. No automatic posting.</span></div>
      </div>
    </section>
  </main>
  <script>
    const tweet = document.getElementById("tweet");
    const style = document.getElementById("style");
    const language = document.getElementById("language");
    const statusEl = document.getElementById("status");
    const replies = document.getElementById("replies");
    const provider = document.getElementById("provider");
    const generate = document.getElementById("generate");

    fetch("/api/key/status").then((r) => r.json()).then((data) => {
      const llm = document.getElementById("llm");
      llm.className = data.configured ? "pill ok" : "pill bad";
      llm.textContent = data.configured ? "LLM connected" : "Missing LLM key";
    }).catch(() => {
      const llm = document.getElementById("llm");
      llm.className = "pill bad";
      llm.textContent = "Unavailable";
    });

    document.getElementById("clear").addEventListener("click", () => {
      tweet.value = "";
      replies.innerHTML = '<p class="empty">Generated replies will appear here. Use Copy to paste one into X manually.</p>';
      provider.textContent = "Ready";
      setStatus("");
    });

    generate.addEventListener("click", async () => {
      const source = tweet.value.trim();
      if (!source) {
        setStatus("Paste a source post first.", true);
        return;
      }
      generate.disabled = true;
      setStatus("Generating...");
      replies.innerHTML = "";
      try {
        const response = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tweet: source,
            style: style.value,
            language: language.value,
            count: 5,
            max_chars: 220
          })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Generation failed.");
        renderReplies(data.candidates || []);
        provider.textContent = data.provider || "agent";
        setStatus((data.candidates || []).length + " replies generated.");
      } catch (error) {
        setStatus(error.message || "Generation failed.", true);
      } finally {
        generate.disabled = false;
      }
    });

    function renderReplies(items) {
      replies.innerHTML = "";
      if (!items.length) {
        replies.innerHTML = '<p class="empty">No replies returned.</p>';
        return;
      }
      for (const item of items) {
        const card = document.createElement("article");
        card.className = "card";
        const top = document.createElement("div");
        top.className = "card-top";
        const angle = document.createElement("span");
        angle.className = "angle";
        angle.textContent = item.angle || "reply";
        const copy = document.createElement("button");
        copy.type = "button";
        copy.textContent = "Copy";
        copy.addEventListener("click", async () => {
          await navigator.clipboard.writeText(item.text || "");
          copy.textContent = "Copied";
          setTimeout(() => copy.textContent = "Copy", 1000);
        });
        const text = document.createElement("p");
        text.className = "reply";
        text.textContent = item.text || "";
        top.appendChild(angle);
        top.appendChild(copy);
        card.appendChild(top);
        card.appendChild(text);
        replies.appendChild(card);
      }
    }

    function setStatus(message, isError) {
      statusEl.textContent = message || "";
      statusEl.classList.toggle("error", Boolean(isError));
    }
  </script>
</body>
</html>`;
}

function renderExtensionHtml(origin) {
  const info = extensionInfo(origin);
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>XCA Extension</title>
  <style>
    * { box-sizing: border-box; letter-spacing: 0; }
    body { margin: 0; background: #f6f4ee; color: #26231f; font: 14px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 820px; margin: 0 auto; padding: 34px 18px; }
    h1 { margin: 0 0 8px; font-size: 25px; }
    p { color: #6c6258; line-height: 1.55; }
    .panel { border: 1px solid #ded7cc; border-radius: 8px; background: #fffdf8; padding: 18px; box-shadow: 0 16px 46px rgba(49, 40, 31, .08); }
    .row { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid #eee6da; }
    .row:first-child { border-top: 0; }
    code { background: #f3eee6; border-radius: 5px; padding: 2px 5px; overflow-wrap: anywhere; }
    .button { min-height: 38px; border: 1px solid #8a5b3d; border-radius: 7px; background: #8a5b3d; color: #fffaf2; padding: 0 14px; font-weight: 760; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }
    ol { color: #4c443d; line-height: 1.65; padding-left: 20px; }
  </style>
</head>
<body>
  <main>
    <h1>Install X Comment Agent</h1>
    <p>Download the extension package from Cloudflare, unzip it, then load it in Chrome.</p>
    <section class="panel">
      <a class="button" href="${escapeHtml(info.download_url)}">Download extension zip</a>
      <ol>
        <li>Download and unzip the package.</li>
        <li>Open <code>chrome://extensions</code>.</li>
        <li>Enable Developer mode.</li>
        <li>Click <code>Load unpacked</code> and select the unzipped folder.</li>
      </ol>
    </section>
  </main>
</body>
</html>`;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

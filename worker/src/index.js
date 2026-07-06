const DEFAULT_LLM_BASE_URL = "https://api.deepseek.com";
const DEFAULT_LLM_MODEL = "deepseek-v4-pro";
const DEFAULT_PERSONA = "practical operator, curious builder, concise and natural";
const DEFAULT_COUNT = 5;
const DEFAULT_MAX_CHARS = 220;

const STYLE_PRESETS = {
  natural: {
    label: "Natural",
    prompt:
      "Concise, specific, conversational, and low-drama. Sound like a real person replying under the post."
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
        return htmlResponse(renderConsoleHtml());
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

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization"
  };
}

function renderConsoleHtml() {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>X Comment Agent</title>
  <style>
    body { margin: 0; background: #f7f4ee; color: #27231f; font: 14px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 780px; margin: 0 auto; padding: 44px 18px; }
    h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }
    p { color: #6a5f54; line-height: 1.55; }
    .panel { border: 1px solid #ded7cc; border-radius: 8px; background: #fffdf8; padding: 18px; box-shadow: 0 16px 46px rgba(49, 40, 31, 0.08); }
    .row { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid #eee6da; }
    .row:first-child { border-top: 0; }
    code { background: #f3eee6; border-radius: 5px; padding: 2px 5px; }
    .ok { color: #067647; font-weight: 700; }
    .bad { color: #b42318; font-weight: 700; }
  </style>
</head>
<body>
  <main>
    <h1>X Comment Agent</h1>
    <p>Cloudflare Worker backend for generating human-reviewed X reply drafts. No X API. No automatic posting.</p>
    <section class="panel">
      <div class="row"><strong>Health</strong><span class="ok">Online</span></div>
      <div class="row"><strong>Generate API</strong><code>POST /api/generate</code></div>
      <div class="row"><strong>LLM status</strong><span id="llm">Checking...</span></div>
    </section>
  </main>
  <script>
    fetch("/api/key/status").then((r) => r.json()).then((data) => {
      document.getElementById("llm").className = data.configured ? "ok" : "bad";
      document.getElementById("llm").textContent = data.configured ? "Connected" : "Missing secret";
    }).catch(() => {
      document.getElementById("llm").className = "bad";
      document.getElementById("llm").textContent = "Unavailable";
    });
  </script>
</body>
</html>`;
}

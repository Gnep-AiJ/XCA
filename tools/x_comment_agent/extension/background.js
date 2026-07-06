const AGENT_ENDPOINTS = [
  "http://192.168.31.188:8765/api/generate",
  "http://127.0.0.1:8765/api/generate",
  "http://localhost:8765/api/generate"
];
const CONTROL_PANEL_URLS = AGENT_ENDPOINTS.map((endpoint) => endpoint.replace("/api/generate", "/"));

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message) {
    return false;
  }

  if (message.type === "XCA_GENERATE") {
    generate(message.payload)
      .then((payload) => sendResponse({ ok: true, payload }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  if (message.type === "XCA_CONTROL_PANEL") {
    resolveControlPanelUrl()
      .then((payload) => sendResponse({ ok: true, payload }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  return false;
});

async function generate(payload) {
  return postJson("/api/generate", payload);
}

async function postJson(path, payload) {
  let lastError = null;
  const attempted = [];

  for (const endpoint of AGENT_ENDPOINTS) {
    const url = endpoint.replace("/api/generate", path);
    attempted.push(url);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `Agent returned HTTP ${response.status}`);
      }
      return data;
    } catch (error) {
      lastError = error;
    }
  }

  throw new Error(
    `Cannot reach local agent. Tried: ${attempted.join(", ")}. ${lastError ? lastError.message : ""}`.trim()
  );
}

async function resolveControlPanelUrl() {
  for (const url of CONTROL_PANEL_URLS) {
    try {
      const response = await fetch(`${url.replace(/\/$/, "")}/health`);
      if (response.ok) {
        return { url };
      }
    } catch (_error) {
      // Try next configured endpoint.
    }
  }
  return { url: CONTROL_PANEL_URLS[0] };
}

const DEFAULT_AGENT_ORIGIN = "https://xca-agent.YOUR_SUBDOMAIN.workers.dev";
const AGENT_ORIGINS = [DEFAULT_AGENT_ORIGIN];

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message) {
    return false;
  }

  if (message.type === "XCA_GENERATE") {
    postJson("/api/generate", message.payload)
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

async function postJson(path, payload) {
  let lastError = null;
  const attempted = [];

  for (const origin of AGENT_ORIGINS) {
    const url = `${origin.replace(/\/$/, "")}${path}`;
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
    `Cannot reach Cloudflare agent. Tried: ${attempted.join(", ")}. ${lastError ? lastError.message : ""}`.trim()
  );
}

async function resolveControlPanelUrl() {
  for (const origin of AGENT_ORIGINS) {
    try {
      const url = origin.replace(/\/$/, "");
      const response = await fetch(`${url}/health`);
      if (response.ok) {
        return { url: `${url}/` };
      }
    } catch (_error) {
      // Try next configured endpoint.
    }
  }
  return { url: `${AGENT_ORIGINS[0].replace(/\/$/, "")}/` };
}

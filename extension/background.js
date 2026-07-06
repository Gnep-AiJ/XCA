const DEFAULT_AGENT_ORIGIN = "https://xca-agent.YOUR_SUBDOMAIN.workers.dev";
const AGENT_ORIGINS = [DEFAULT_AGENT_ORIGIN];
const EXTENSION_VERSION = "0.1.0";
let extensionInfoCache = null;

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

  if (message.type === "XCA_EXTENSION_INFO") {
    getExtensionInfo()
      .then((payload) => sendResponse({ ok: true, payload }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  return false;
});

async function postJson(path, payload) {
  let lastError = null;
  const attempted = [];
  const info = await getExtensionInfo();
  const origins = orderedOrigins(info && info.worker_origin);

  for (const origin of origins) {
    const url = path === "/api/generate" && info && info.generate_url
      ? info.generate_url
      : `${origin.replace(/\/$/, "")}${path}`;
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
  const info = await getExtensionInfo();
  if (info && info.control_panel_url) {
    return { url: info.control_panel_url };
  }
  for (const origin of orderedOrigins(info && info.worker_origin)) {
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

async function getExtensionInfo() {
  if (extensionInfoCache) {
    return extensionInfoCache;
  }

  for (const origin of AGENT_ORIGINS) {
    try {
      const url = `${origin.replace(/\/$/, "")}/api/extension/info`;
      const response = await fetch(url, { method: "GET" });
      if (!response.ok) {
        continue;
      }
      const data = await response.json();
      extensionInfoCache = {
        version: data.version || EXTENSION_VERSION,
        worker_origin: data.worker_origin || origin,
        control_panel_url: data.control_panel_url || `${origin.replace(/\/$/, "")}/`,
        download_url: data.download_url || `${origin.replace(/\/$/, "")}/extension`,
        update_check_url: data.update_check_url || url,
        generate_url: data.generate_url || `${origin.replace(/\/$/, "")}/api/generate`
      };
      return extensionInfoCache;
    } catch (_error) {
      // Try the next configured origin.
    }
  }

  extensionInfoCache = {
    version: EXTENSION_VERSION,
    worker_origin: AGENT_ORIGINS[0],
    control_panel_url: `${AGENT_ORIGINS[0].replace(/\/$/, "")}/`,
    download_url: `${AGENT_ORIGINS[0].replace(/\/$/, "")}/extension`,
    update_check_url: `${AGENT_ORIGINS[0].replace(/\/$/, "")}/api/extension/info`,
    generate_url: `${AGENT_ORIGINS[0].replace(/\/$/, "")}/api/generate`
  };
  return extensionInfoCache;
}

function orderedOrigins(preferredOrigin) {
  const origins = preferredOrigin ? [preferredOrigin, ...AGENT_ORIGINS] : AGENT_ORIGINS;
  return Array.from(new Set(origins.map((origin) => origin.replace(/\/$/, ""))));
}

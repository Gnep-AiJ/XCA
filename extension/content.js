(() => {
  const ROOT_ID = "xca-root";
  const DEFAULT_PERSONA = "practical operator, curious builder, concise and natural";
  const DEFAULT_COUNT = 5;
  const DEFAULT_MAX_CHARS = 220;

  if (document.getElementById(ROOT_ID)) {
    return;
  }

  const root = document.createElement("div");
  root.id = ROOT_ID;
  root.className = "xca-root";
  root.innerHTML = `
    <button class="xca-toggle" type="button" title="Open Reply Assistant"><span>AI</span><strong>Reply</strong></button>
    <section class="xca-panel xca-hidden" aria-label="X Comment Agent">
      <div class="xca-head">
        <h2 class="xca-title">Reply Assistant</h2>
        <button class="xca-close" type="button" aria-label="Close">×</button>
      </div>
      <div class="xca-body">
        <div class="xca-toolbar">
          <button class="xca-button primary" type="button" data-action="generate">Generate Reply</button>
          <button class="xca-button" type="button" data-action="console">Open Control Panel</button>
        </div>
        <p class="xca-status" role="status"></p>
        <div class="xca-list"></div>
      </div>
    </section>
  `;
  document.documentElement.appendChild(root);

  const toggle = root.querySelector(".xca-toggle");
  const panel = root.querySelector(".xca-panel");
  const close = root.querySelector(".xca-close");
  const status = root.querySelector(".xca-status");
  const list = root.querySelector(".xca-list");
  const generateButton = root.querySelector('[data-action="generate"]');

  toggle.addEventListener("click", () => setOpen(true));
  close.addEventListener("click", () => setOpen(false));

  root.querySelector('[data-action="console"]').addEventListener("click", async () => {
    try {
      const response = await chrome.runtime.sendMessage({ type: "XCA_CONTROL_PANEL" });
      if (!response || !response.ok || !response.payload || !response.payload.url) {
        throw new Error((response && response.error) || "Control panel unavailable.");
      }
      window.open(response.payload.url, "_blank", "noopener,noreferrer");
    } catch (error) {
      setStatus(error.message || "Control panel unavailable.", true);
    }
  });

  generateButton.addEventListener("click", () => {
    const source = readCurrentTweet();
    if (!source.text) {
      setStatus("Could not identify the current tweet. Select the text and try Generate Reply.", true);
      return;
    }
    generateFromSource(source);
  });

  async function generateFromSource(source) {
    generateButton.disabled = true;
    setStatus("Generating...");
    list.innerHTML = "";

    const payload = {
      tweet: source.text,
      context: source.context || "",
      persona: DEFAULT_PERSONA,
      language: "auto",
      style: "natural",
      count: DEFAULT_COUNT,
      max_chars: DEFAULT_MAX_CHARS
    };

    try {
      const response = await chrome.runtime.sendMessage({ type: "XCA_GENERATE", payload });
      if (!response || !response.ok) {
        throw new Error((response && response.error) || "Generation failed.");
      }
      const candidates = response.payload.candidates || [];
      renderCandidates(candidates);
      const language = response.payload.language === "zh" ? "Chinese" : "English";
      const warning = response.payload.warning ? " Fallback rules used." : "";
      setStatus(`${candidates.length} ${language} replies generated.${warning}`);
    } catch (error) {
      setStatus(error.message || "Generation failed.", true);
    } finally {
      generateButton.disabled = false;
    }
  }

  function setOpen(open) {
    panel.classList.toggle("xca-hidden", !open);
  }

  function readCurrentTweet() {
    const selection = window.getSelection();
    const selected = String(selection ? selection.toString() : "").trim();
    if (selected && selected.length >= 12) {
      return { text: cleanText(selected), context: "" };
    }

    const statusId = getStatusId();
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
    const candidates = [];

    for (const article of articles) {
      const tweetText = article.querySelector('[data-testid="tweetText"]');
      const text = cleanText(tweetText ? tweetText.innerText : "");
      if (!text) {
        continue;
      }
      const links = Array.from(article.querySelectorAll('a[href*="/status/"]')).map((link) => link.getAttribute("href") || "");
      const hasStatus = statusId ? links.some((href) => href.includes(`/status/${statusId}`)) : false;
      const rect = article.getBoundingClientRect();
      candidates.push({
        index: articles.indexOf(article),
        text,
        hasStatus,
        topDistance: Math.abs(rect.top),
        length: text.length
      });
    }

    if (!candidates.length) {
      return { text: "", context: "" };
    }

    candidates.sort((a, b) => {
      if (a.hasStatus !== b.hasStatus) {
        return a.hasStatus ? -1 : 1;
      }
      return a.topDistance - b.topDistance || b.length - a.length;
    });

    const target = candidates[0];
    return {
      text: target.text,
      context: buildThreadContext(articles, target.index)
    };
  }

  function buildThreadContext(articles, targetIndex) {
    if (targetIndex <= 0) {
      return "";
    }
    const previous = articles
      .slice(Math.max(0, targetIndex - 4), targetIndex)
      .map((article) => {
        const tweetText = article.querySelector('[data-testid="tweetText"]');
        return cleanText(tweetText ? tweetText.innerText : "");
      })
      .filter(Boolean);

    return previous.map((text, index) => `Context ${index + 1}: ${text}`).join("\n");
  }

  function getStatusId() {
    const match = location.pathname.match(/\/status\/(\d+)/);
    return match ? match[1] : "";
  }

  function cleanText(text) {
    return String(text || "")
      .replace(/\s+\n/g, "\n")
      .replace(/\n\s+/g, "\n")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
  }

  function renderCandidates(candidates) {
    list.innerHTML = "";
    if (!candidates.length) {
      list.innerHTML = '<p class="xca-status">No candidates returned.</p>';
      return;
    }

    for (const candidate of candidates) {
      const card = document.createElement("article");
      card.className = "xca-card";

      const top = document.createElement("div");
      top.className = "xca-card-top";

      const badges = document.createElement("div");
      badges.className = "xca-badges";
      badges.appendChild(makeBadge(candidate.angle || "reply"));

      const copy = document.createElement("button");
      copy.className = "xca-button";
      copy.type = "button";
      copy.textContent = "Copy";
      copy.addEventListener("click", async () => {
        await navigator.clipboard.writeText(candidate.text || "");
        copy.textContent = "Copied";
        setTimeout(() => {
          copy.textContent = "Copy";
        }, 1100);
      });

      const text = document.createElement("p");
      text.className = "xca-card-text";
      text.textContent = candidate.text || "";

      top.appendChild(badges);
      top.appendChild(copy);
      card.appendChild(top);
      card.appendChild(text);
      list.appendChild(card);
    }
  }

  function makeBadge(text) {
    const badge = document.createElement("span");
    badge.className = "xca-badge";
    badge.textContent = text;
    return badge;
  }

  function setStatus(message, isError = false) {
    status.textContent = message || "";
    status.classList.toggle("error", Boolean(isError));
  }
})();

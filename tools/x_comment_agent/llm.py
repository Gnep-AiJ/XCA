from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from typing import Any

from .agent import CommentCandidate, CommentRequest, NATURAL_REPLY_PROMPT, risk_level
from .styles import ReplyStyle


DEFAULT_LLM_BASE_URL = "https://api.deepseek.com"
DEFAULT_LLM_MODEL = "deepseek-v4-pro"
DEEPSEEK_API_URL = f"{DEFAULT_LLM_BASE_URL}/chat/completions"
DEFAULT_DEEPSEEK_MODEL = DEFAULT_LLM_MODEL
SYSTEM_PROMPT = f"""
You are a senior social media operator helping draft X replies.

{NATURAL_REPLY_PROMPT}

Output exactly valid JSON. No markdown. No extra text.
Return one object with a "replies" array. Each item has:
- angle: short label
- text: natural reply
- translation_zh: concise Chinese translation or reading aid

Rules:
- Generate exactly 5 replies.
- Write only in the target language.
- Keep "text" clean and copy-ready. It must not include translations, labels, explanations, bullets, or quote marks around the reply.
- If the target language is English, fill "translation_zh" with a natural Chinese translation of the reply so a Chinese operator can understand it before copying. Do not include this Chinese text in "text".
- If the target language is Chinese, set "translation_zh" to an empty string.
- Each reply should be 1-2 short sentences.
- Sound like a real person replying under the post, not an article summary.
- Anchor every reply to a concrete idea from the source post.
- If thread, timeline, image, URL, or time context is provided, use it only to understand the situation. Reply to the source post itself.
- Infer the right mode from context: witty when the post is playful or meme-like, thoughtful when it makes a serious claim, technical when it discusses implementation, skeptical when claims are overconfident, supportive when the author shares progress.
- Use image context only when it clearly changes the meaning of the post. Never pretend to see image details that were not provided.
- Mix angles: add-on, question, soft disagreement, operator view, product/metric angle.
- No hashtags, no links, no @mentions, no "follow me", no sales pitch.
- Do not claim private facts or make unverifiable promises.
""".strip()


@dataclass(frozen=True)
class LLMResult:
    candidates: list[CommentCandidate]
    provider: str


class DeepSeekClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        load_env_file()
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "").strip() or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        self.model = model or os.environ.get("LLM_MODEL", "").strip() or os.environ.get("DEEPSEEK_MODEL", DEFAULT_LLM_MODEL).strip()
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_LLM_BASE_URL
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def generate_replies(self, request: CommentRequest, target_language: str, style: ReplyStyle) -> LLMResult:
        if not self.enabled:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source_post": request.tweet,
                            "thread_context": request.context,
                            "timeline_context": request.timeline_context,
                            "image_context": request.image_context,
                            "post_time": request.post_time,
                            "page_url": request.page_url,
                            "persona": request.persona,
                            "reply_style": {
                                "key": style.key,
                                "label": style.label,
                                "instruction": style.prompt,
                            },
                            "target_language": "Chinese" if target_language == "zh" else "English",
                            "count": 5,
                            "max_chars": request.max_chars,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.85,
            "top_p": 0.9,
            "max_tokens": 1200,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        if self.is_deepseek_pro:
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = "high"
        try:
            replies = self._generate_with_payload(payload)
        except (json.JSONDecodeError, RuntimeError):
            if not self.is_deepseek_pro:
                raise
            retry_payload = dict(payload)
            retry_payload.pop("thinking", None)
            retry_payload.pop("reasoning_effort", None)
            replies = self._generate_with_payload(retry_payload)

        candidates: list[CommentCandidate] = []
        for index, item in enumerate(replies[:5], start=1):
            angle = str(item.get("angle") or f"reply {index}").strip()
            text = clean_reply(str(item.get("text") or item.get("reply") or item.get("comment") or ""))
            translation = clean_translation(
                str(item.get("translation_zh") or item.get("translation") or item.get("zh") or "")
            )
            if not text:
                continue
            candidates.append(
                CommentCandidate(
                    angle=angle,
                    text=text,
                    score=90 - index,
                    risk=risk_level(text),
                    translation=translation if target_language == "en" else "",
                )
            )

        if len(candidates) != 5:
            raise RuntimeError("DeepSeek returned an unexpected candidate count")
        return LLMResult(candidates=candidates, provider=f"{self.provider_name}:{self.model}")

    @property
    def is_deepseek_pro(self) -> bool:
        return "api.deepseek.com" in self.base_url and self.model == "deepseek-v4-pro"

    @property
    def provider_name(self) -> str:
        if "api.deepseek.com" in self.base_url:
            return "deepseek"
        return "openai-compatible"

    def _generate_with_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = self._post(payload)
        content = response["choices"][0]["message"].get("content") or ""
        if not content.strip():
            raise RuntimeError("DeepSeek returned empty content")
        return parse_replies(content)

    def generate_bilingual(self, request: CommentRequest) -> LLMResult:
        from .styles import get_style

        return self.generate_replies(request, "zh", get_style("natural"))

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.chat_completions_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek HTTP {exc.code}: {message[:300]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"DeepSeek network error: {exc.reason}") from exc

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError("DeepSeek returned invalid JSON")
        return parsed

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


def parse_pairs(content: str) -> list[dict[str, Any]]:
    return parse_replies(content)


def parse_replies(content: str) -> list[dict[str, Any]]:
    data = json.loads(extract_json(content))
    if isinstance(data, list):
        replies = data
    elif isinstance(data, dict):
        replies = data.get("replies") or data.get("comments") or data.get("candidates") or []
    else:
        replies = []
    if not isinstance(replies, list):
        raise RuntimeError("DeepSeek JSON does not contain a list")
    return [item for item in replies if isinstance(item, dict)]


def extract_json(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return content


def clean_reply(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[-*\d.、\s]+", "", text)
    return text


def clean_translation(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[-*\d.、\s]+", "", text)
    return text


def max_risk(*risks: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return max(risks, key=lambda item: order.get(item, 0))


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class ReplyStyle:
    key: str
    label: str
    prompt: str


DEFAULT_STYLES = {
    "adaptive": ReplyStyle(
        key="adaptive",
        label="Adaptive",
        prompt=(
            "Context-aware social reply skill. First infer the post's intent, mood, and stakes from source text, thread, time, "
            "timeline, and image context. Be witty when the post is playful, thoughtful when it is serious, technical when it "
            "is implementation-heavy, and politely skeptical when claims are inflated. Keep the reply natural and copy-ready."
        ),
    ),
    "natural": ReplyStyle(
        key="natural",
        label="Natural",
        prompt="Natural, concise, human. Light opinion, no performance, no sales tone.",
    ),
    "sharp": ReplyStyle(
        key="sharp",
        label="Sharp",
        prompt="Sharper and more opinionated, but still respectful. Prefer clear judgment over vague agreement.",
    ),
    "supportive": ReplyStyle(
        key="supportive",
        label="Supportive",
        prompt="Supportive and warm. Add one useful observation without sounding flattering or generic.",
    ),
    "technical": ReplyStyle(
        key="technical",
        label="Technical",
        prompt="Technical operator style. Mention concrete implementation, evaluation, workflow, metrics, or tradeoffs when relevant.",
    ),
    "curious": ReplyStyle(
        key="curious",
        label="Curious",
        prompt="Curious and conversational. Prefer thoughtful questions that invite the author to expand.",
    ),
}


def get_style(style_key: str | None) -> ReplyStyle:
    styles = load_styles()
    key = (style_key or "natural").strip().lower()
    return styles.get(key) or styles["natural"]


def list_styles() -> list[dict[str, str]]:
    return [
        {"key": style.key, "label": style.label}
        for style in load_styles().values()
    ]


def styles_config() -> dict[str, list[dict[str, object]]]:
    loaded = load_styles()
    return {
        "styles": [
            {
                "key": style.key,
                "label": style.label,
                "prompt": style.prompt,
                "builtin": style.key in DEFAULT_STYLES,
            }
            for style in loaded.values()
        ]
    }


def save_styles_config(items: Any) -> dict[str, list[dict[str, object]]]:
    if not isinstance(items, list):
        raise ValueError("styles must be a list")

    cleaned: dict[str, dict[str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = normalize_style_key(str(item.get("key") or ""))
        label = str(item.get("label") or key.title()).strip()
        prompt = str(item.get("prompt") or "").strip()
        if not key or not prompt:
            continue
        if len(label) > 40:
            raise ValueError(f"style label is too long: {key}")
        if len(prompt) > 600:
            raise ValueError(f"style prompt is too long: {key}")

        default = DEFAULT_STYLES.get(key)
        if default and default.label == label and default.prompt == prompt:
            continue
        cleaned[key] = {"label": label, "prompt": prompt}

    path = styles_path()
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return styles_config()


def load_styles() -> dict[str, ReplyStyle]:
    styles = dict(DEFAULT_STYLES)
    path = styles_path()
    if not path.exists():
        return styles

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return styles

    if not isinstance(raw, dict):
        return styles

    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        prompt = str(value.get("prompt") or "").strip()
        if not prompt:
            continue
        normalized_key = str(key).strip().lower()
        styles[normalized_key] = ReplyStyle(
            key=normalized_key,
            label=str(value.get("label") or normalized_key.title()).strip(),
            prompt=prompt,
        )
    return styles


def styles_path() -> Path:
    return Path(__file__).resolve().parent / "styles.json"


def normalize_style_key(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-_")
    return value[:32]

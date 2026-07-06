from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
from typing import Iterable


DEFAULT_PERSONA = "practical operator, curious builder, concise and natural"
DEFAULT_COUNT = 5
DEFAULT_MAX_CHARS = 220

NATURAL_REPLY_PROMPT = """
Read the source post first, then draft replies that sound like a real person
joining the conversation. Anchor the reply to one concrete phrase or tension in
the post. Prefer one or two short sentences. Avoid slogans, sales language,
generic praise, excessive certainty, and obvious AI summary style.
""".strip()

FORBIDDEN_PHRASES = (
    "关注我",
    "私信我",
    "稳赚",
    "百分百",
    "100%",
    " guaranteed ",
    "follow me",
    "dm me",
)

URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#([\w\u4e00-\u9fff]+)")
ASCII_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{2,}")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


@dataclass(frozen=True)
class CommentRequest:
    tweet: str
    persona: str = DEFAULT_PERSONA
    count: int = DEFAULT_COUNT
    max_chars: int = DEFAULT_MAX_CHARS
    language: str = "auto"
    context: str = ""
    timeline_context: str = ""
    image_context: str = ""
    post_time: str = ""
    page_url: str = ""


@dataclass(frozen=True)
class CommentCandidate:
    angle: str
    text: str
    score: int
    risk: str
    translation: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class CommentAgent:
    """Rule-based comment drafter optimized for human-reviewed X replies."""

    def generate(self, request: CommentRequest) -> list[CommentCandidate]:
        tweet = normalize_text(request.tweet)
        if not tweet:
            raise ValueError("tweet text is required")

        context = _Context.from_tweet(tweet, request.persona)
        language = resolve_language(tweet, request.language)
        templates = self._zh_templates(context) if language == "zh" else self._en_templates(context)

        candidates: list[CommentCandidate] = []
        seen: set[str] = set()
        for angle, template in templates:
            text = fit_length(template, request.max_chars)
            text = remove_forbidden_phrases(text)
            fingerprint = _fingerprint(text)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            candidates.append(
                CommentCandidate(
                    angle=angle,
                    text=text,
                    score=score_comment(text, context),
                    risk=risk_level(text),
                )
            )

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[: max(1, min(request.count, 12))]

    def _zh_templates(self, context: "_Context") -> list[tuple[str, str]]:
        topic = context.topic
        detail = context.detail
        tension = context.tension
        anchor = context.anchor
        return [
            (
                "顺着补充",
                f"这个点我同意，尤其是「{anchor}」这块。很多人会低估后面的{detail}。",
            ),
            (
                "自然追问",
                f"我也在想这个问题：最后真正卡住的会是{tension}，还是大家太早把它讲成大叙事了？",
            ),
            (
                "个人判断",
                f"我会稍微看重落地一点。{topic}能不能成立，最后还是看它有没有变成一个每天都有人用的动作。",
            ),
            (
                "轻微反驳",
                f"方向我认同，但可能没那么快。没有清楚的反馈闭环，{topic}很容易从机会变成噪音。",
            ),
            (
                "运营视角",
                f"从运营角度看，最该盯的不是热度，而是用户会不会为了同一个问题反复回来。",
            ),
            (
                "短评",
                f"这类事最后拼的不是概念新不新，而是{detail}够不够顺。",
            ),
            (
                "指标追问",
                f"如果只看一个指标来判断它是不是真的有用，你会更看留存、节省时间，还是转化？",
            ),
            (
                "产品视角",
                f"我更相信先做窄一点。先在一个具体场景里站住，再谈平台化会靠谱很多。",
            ),
            (
                "共鸣",
                f"这条挺有共鸣。「{anchor}」看起来简单，但真正做起来，细节会把大部分团队筛掉。",
            ),
            (
                "降温",
                f"现在讨论容易偏热，我反而觉得可以先看一个朴素问题：谁会在下周还继续用它？",
            ),
        ]

    def _en_templates(self, context: "_Context") -> list[tuple[str, str]]:
        topic = to_english_term(context.topic)
        detail = to_english_term(context.detail)
        tension = to_english_term(context.tension)
        anchor = context.english_anchor
        return [
            (
                "specific add-on",
                f"That part about {anchor} feels right. The hard bit is usually making it survive {detail}, not just making it look good once.",
            ),
            (
                "question",
                f"Do you think the real bottleneck is {tension}, or that teams turn it into a big narrative before they have small working loops?",
            ),
            (
                "operator take",
                f"I would judge this less by the launch moment and more by whether people come back to solve the same problem next week.",
            ),
            (
                "soft disagreement",
                f"I agree with the direction, but I would be a bit slower to call it solved. Without a tight feedback loop, {topic} turns noisy fast.",
            ),
            (
                "short take",
                f"The key question is not whether the idea is new. It is whether it makes {detail} easy enough to change behavior.",
            ),
            (
                "metric question",
                "If you had to pick one proof point, would you look at retention, time saved, or conversion?",
            ),
            (
                "product angle",
                "I like the narrower version of this more: win one repeated use case first, then earn the right to become a platform.",
            ),
            (
                "grounded caution",
                f"The exciting part is obvious. The less obvious part is how much {tension} decides whether this becomes a habit.",
            ),
        ]


@dataclass(frozen=True)
class _Context:
    topic: str
    detail: str
    tension: str
    anchor: str
    english_anchor: str
    keywords: tuple[str, ...]

    @classmethod
    def from_tweet(cls, tweet: str, persona: str) -> "_Context":
        keywords = extract_keywords(tweet)
        topic = pick_topic(tweet, keywords)
        detail = pick_detail(tweet, persona)
        tension = pick_tension(tweet)
        raw_anchor = pick_anchor(tweet, keywords, topic)
        return cls(
            topic=topic,
            detail=detail,
            tension=tension,
            anchor=to_chinese_term(raw_anchor),
            english_anchor=to_english_term(raw_anchor),
            keywords=tuple(keywords),
        )


def normalize_text(text: str) -> str:
    text = URL_RE.sub("", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def resolve_language(text: str, language: str | None = "auto") -> str:
    requested = (language or "auto").lower()
    if requested in {"zh", "en"}:
        return requested
    return detect_language(text)


def detect_language(text: str) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return "en"
    cjk_count = len(CJK_RE.findall(normalized))
    latin_count = len(re.findall(r"[A-Za-z]", normalized))
    return "zh" if cjk_count >= max(4, latin_count // 3) else "en"


def extract_keywords(text: str) -> list[str]:
    hashtags = HASHTAG_RE.findall(text)
    words = [word for word in ASCII_WORD_RE.findall(text) if word.lower() not in _stopwords()]
    cjk_chunks = _extract_cjk_chunks(text)
    merged = [*hashtags, *words, *cjk_chunks]
    return _dedupe([item.strip("_- ") for item in merged if len(item.strip("_- ")) >= 2])[:8]


def pick_topic(tweet: str, keywords: Iterable[str]) -> str:
    lowered = tweet.lower()
    if "open source" in lowered or "github" in lowered or "开源" in tweet:
        return "开源项目"
    if "agent" in lowered or "agents" in lowered or "智能体" in tweet:
        return "Agent"
    if "ai" in lowered or "llm" in lowered or "模型" in tweet:
        return "AI 产品"
    if "startup" in lowered or "founder" in lowered or "创业" in tweet:
        return "创业"
    for keyword in keywords:
        return keyword
    return "这件事"


def pick_detail(tweet: str, persona: str) -> str:
    lowered = f"{tweet} {persona}".lower()
    if "growth" in lowered or "distribution" in lowered or "运营" in tweet:
        return "分发和转化"
    if "github" in lowered or "open source" in lowered or "开源" in tweet:
        return "社区采用"
    if "agent" in lowered or "workflow" in lowered:
        return "真实工作流"
    if "eval" in lowered or "quality" in lowered:
        return "评估体系"
    return "具体场景"


def pick_tension(tweet: str) -> str:
    lowered = tweet.lower()
    if "growth" in lowered or "distribution" in lowered:
        return "分发效率"
    if "open source" in lowered or "github" in lowered or "开源" in tweet:
        return "从 star 到真实使用的转化"
    if "agent" in lowered:
        return "可靠性"
    if "ai" in lowered or "llm" in lowered:
        return "幻觉和成本"
    return "执行细节"


def pick_anchor(tweet: str, keywords: Iterable[str], topic: str) -> str:
    for quoted in re.findall(r"[\"'“”‘’]([^\"'“”‘’]{3,40})[\"'“”‘’]", tweet):
        return trim_anchor(quoted.strip())

    lowered = tweet.lower()
    phrase_candidates = (
        ("open source", "open source"),
        ("ai agents", "AI agents"),
        ("agentic", "agentic workflow"),
        ("distribution", "distribution"),
        ("reliability", "reliability"),
        ("evals", "evals"),
        ("github stars", "GitHub stars"),
        ("workflow", "workflow"),
    )
    for needle, phrase in phrase_candidates:
        if needle in lowered:
            return phrase

    for keyword in keywords:
        if keyword.lower() not in {"the", "this", "that", "open", "source", "agent", "agents", "products"}:
            return keyword

    if "demo" in lowered:
        return "demo"
    return topic


def trim_anchor(text: str, max_chars: int = 28) -> str:
    text = normalize_text(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip(" ，,。.")


def fit_length(text: str, max_chars: int) -> str:
    max_chars = max(80, max_chars)
    if len(text) <= max_chars:
        return text
    trimmed = text[: max_chars - 1].rstrip(" ，,。.")
    return f"{trimmed}…"


def polish_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("。。", "。").replace("..", ".")
    text = re.sub(r"^(同意。|Agree\.)\s*", "", text)
    return text


def remove_forbidden_phrases(text: str) -> str:
    cleaned = text
    lowered = f" {cleaned.lower()} "
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered or phrase in cleaned:
            cleaned = re.sub(re.escape(phrase.strip()), "", cleaned, flags=re.IGNORECASE)
            lowered = f" {cleaned.lower()} "
    return polish_text(cleaned)


def score_comment(text: str, context: _Context) -> int:
    score = 50
    if "？" in text or "?" in text:
        score += 8
    if context.anchor and context.anchor in text:
        score += 12
    if context.topic in text:
        score += 5
    if context.detail in text:
        score += 6
    if 40 <= len(text) <= 180:
        score += 10
    if any(keyword in text for keyword in ("反馈", "留存", "转化", "细节", "habit", "retention", "conversion", "behavior")):
        score += 8
    if any(keyword in text for keyword in ("这个判断很准", "可以再补一层", "真正有价值的是")):
        score -= 16
    if len(text) > 210:
        score -= 8
    if risk_level(text) != "low":
        score -= 20
    return score


def risk_level(text: str) -> str:
    lowered = f" {text.lower()} "
    if any(phrase in lowered or phrase in text for phrase in FORBIDDEN_PHRASES):
        return "high"
    if len(HASHTAG_RE.findall(text)) > 2 or len(MENTION_RE.findall(text)) > 1:
        return "medium"
    if "http://" in lowered or "https://" in lowered:
        return "medium"
    return "low"


def to_english_term(term: str) -> str:
    mapping = {
        "这件事": "this shift",
        "开源项目": "open source projects",
        "AI 产品": "AI products",
        "创业": "startup building",
        "真实工作流": "real workflows",
        "分发和转化": "distribution and conversion",
        "社区采用": "community adoption",
        "评估体系": "evaluation systems",
        "具体场景": "specific use cases",
        "可靠性": "reliability",
        "从 star 到真实使用的转化": "conversion from stars to real usage",
        "幻觉和成本": "hallucination and cost",
        "分发效率": "distribution efficiency",
        "执行细节": "execution details",
        "细节": "details",
        "热度": "hype",
        "open source": "open source",
        "AI agents": "AI agents",
        "evals": "evals",
        "GitHub stars": "GitHub stars",
    }
    return mapping.get(term, term)


def to_chinese_term(term: str) -> str:
    mapping = {
        "open source": "开源",
        "AI agents": "AI agents",
        "agentic workflow": "Agent 工作流",
        "distribution": "分发",
        "reliability": "可靠性",
        "evals": "评估",
        "GitHub stars": "GitHub stars",
        "workflow": "工作流",
    }
    return mapping.get(term, term)


def _extract_cjk_chunks(text: str) -> list[str]:
    if not CJK_RE.search(text):
        return []
    chunks = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    return [chunk for chunk in chunks if chunk not in _cjk_stopwords()]


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _fingerprint(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _stopwords() -> set[str]:
    return {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "you",
        "your",
        "about",
        "into",
        "need",
        "needs",
    }


def _cjk_stopwords() -> set[str]:
    return {"这个", "一个", "不是", "但是", "如果", "因为", "所以", "可以", "真的", "可能", "什么"}

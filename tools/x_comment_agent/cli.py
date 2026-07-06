from __future__ import annotations

import argparse
import json
import sys

from .agent import CommentAgent, CommentRequest, DEFAULT_COUNT, DEFAULT_MAX_CHARS, DEFAULT_PERSONA


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="x-comment-agent",
        description="Generate human-reviewed X reply candidates without using the X API.",
    )
    parser.add_argument("--tweet", help="Source post text. If omitted, stdin is used.")
    parser.add_argument("--persona", default=DEFAULT_PERSONA)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--language", choices=["zh", "en", "both"], default="both")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    tweet = args.tweet if args.tweet is not None else sys.stdin.read()
    request = CommentRequest(
        tweet=tweet,
        persona=args.persona,
        count=args.count,
        max_chars=args.max_chars,
        language=args.language,
    )

    try:
        if args.language == "both":
            zh_candidates = CommentAgent().generate(CommentRequest(**{**request.__dict__, "language": "zh"}))
            en_candidates = CommentAgent().generate(CommentRequest(**{**request.__dict__, "language": "en"}))
            candidates = [*zh_candidates, *en_candidates]
        else:
            candidates = CommentAgent().generate(request)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps([candidate.to_dict() for candidate in candidates], ensure_ascii=False, indent=2))
        return 0

    for index, candidate in enumerate(candidates, start=1):
        print(f"{index}. [{candidate.angle} | score={candidate.score} | risk={candidate.risk}]")
        print(candidate.text)
        if index != len(candidates):
            print()
    return 0

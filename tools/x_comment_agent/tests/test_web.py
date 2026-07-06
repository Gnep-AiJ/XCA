import unittest
import re

from tools.x_comment_agent.web import generate_candidates


class WebGenerationTests(unittest.TestCase):
    def test_auto_language_generates_english_candidates_for_english_source(self):
        candidates = generate_candidates(
            {
                "tweet": "AI agents need evals more than demos.",
                "language": "auto",
                "count": 2,
                "max_chars": 160,
                "use_llm": False,
            }
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual({"English"}, {candidate["language"] for candidate in candidates})

    def test_auto_language_generates_chinese_candidates_for_chinese_source(self):
        candidates = generate_candidates(
            {
                "tweet": "Agent 真正难的不是 demo，而是上线后的可靠性和评估。",
                "language": "auto",
                "count": 2,
                "use_llm": False,
            }
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual({"中文"}, {candidate["language"] for candidate in candidates})

    def test_english_candidates_do_not_include_cjk_context_terms(self):
        candidates = generate_candidates(
            {
                "tweet": "AI agents need evals more than demos.",
                "language": "en",
                "count": 3,
                "use_llm": False,
            }
        )

        self.assertFalse(any(re.search(r"[\u4e00-\u9fff]", candidate["text"]) for candidate in candidates))

    def test_rejects_empty_tweet(self):
        with self.assertRaises(ValueError):
            generate_candidates({"tweet": "  "})

    def test_defaults_to_source_language_generation(self):
        candidates = generate_candidates(
            {"tweet": "Open source agents are becoming distribution channels.", "use_llm": False}
        )

        self.assertEqual(len(candidates), 5)
        self.assertEqual({"English"}, {candidate["language"] for candidate in candidates})


if __name__ == "__main__":
    unittest.main()

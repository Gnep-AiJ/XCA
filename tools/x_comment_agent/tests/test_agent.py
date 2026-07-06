import unittest

from tools.x_comment_agent import CommentAgent, CommentRequest


class CommentAgentTests(unittest.TestCase):
    def test_generates_requested_number_of_low_risk_comments(self):
        request = CommentRequest(
            tweet="AI agents need evals more than demos. Reliability is the product.",
            count=5,
            max_chars=180,
        )

        candidates = CommentAgent().generate(request)

        self.assertEqual(len(candidates), 5)
        self.assertTrue(all(candidate.risk == "low" for candidate in candidates))
        self.assertTrue(all(len(candidate.text) <= 180 for candidate in candidates))

    def test_detects_open_source_context(self):
        request = CommentRequest(
            tweet="The best open source projects turn GitHub stars into real distribution.",
            count=3,
        )

        texts = [candidate.text for candidate in CommentAgent().generate(request)]

        self.assertTrue(any("open source" in text.lower() or "star" in text.lower() for text in texts))

    def test_rejects_blank_tweet(self):
        with self.assertRaises(ValueError):
            CommentAgent().generate(CommentRequest(tweet="   "))

    def test_comments_avoid_old_template_phrases(self):
        request = CommentRequest(
            tweet="AI agents need evals more than demos. Reliability is the product.",
            count=6,
            max_chars=220,
        )

        texts = [candidate.text for candidate in CommentAgent().generate(request)]

        joined = "\n".join(texts)
        self.assertNotIn("这个判断很准", joined)
        self.assertNotIn("可以再补一层", joined)
        self.assertTrue(any("？" in text or "?" in text for text in texts))


if __name__ == "__main__":
    unittest.main()

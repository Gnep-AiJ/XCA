import json
import unittest

from tools.x_comment_agent import CommentRequest
from tools.x_comment_agent.llm import DeepSeekClient
from tools.x_comment_agent.styles import get_style


class FakeClient(DeepSeekClient):
    def __init__(self):
        super().__init__(api_key="sk-test", model="test-model", base_url="https://api.example.com")

    def _post(self, payload):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "replies": [
                                    {
                                        "angle": f"angle {index}",
                                        "text": f"Reply {index} about evals.",
                                        "translation_zh": f"关于评估的回复 {index}。",
                                    }
                                    for index in range(1, 6)
                                ]
                            }
                        )
                    }
                }
            ]
        }


class LlmTranslationTests(unittest.TestCase):
    def test_english_generation_keeps_copy_text_and_chinese_translation_separate(self):
        result = FakeClient().generate_replies(
            CommentRequest(tweet="AI agents need evals more than demos."),
            "en",
            get_style("adaptive"),
        )

        self.assertEqual(len(result.candidates), 5)
        self.assertEqual(result.candidates[0].text, "Reply 1 about evals.")
        self.assertEqual(result.candidates[0].translation, "关于评估的回复 1。")

    def test_chinese_generation_omits_translation_helper(self):
        result = FakeClient().generate_replies(
            CommentRequest(tweet="Agent 真正难的是上线后的评估。"),
            "zh",
            get_style("adaptive"),
        )

        self.assertEqual(result.candidates[0].translation, "")


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import app


class TranslationTests(unittest.TestCase):
    def test_same_language_does_not_call_provider(self):
        with patch.object(app, "urlopen") as open_url:
            translated = app.translate_with_provider("Source text.", "en", "en")

        self.assertEqual(translated, "Source text.")
        open_url.assert_not_called()

    def test_long_text_is_translated_in_provider_sized_chunks(self):
        class ProviderResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({
                    "responseStatus": 200,
                    "responseData": {"translatedText": "अनुवाद"},
                }).encode("utf-8")

        source = "word " * 104
        with patch.object(app, "urlopen", return_value=ProviderResponse()) as open_url:
            translated = app.translate_with_provider(source, "en", "ka")

        self.assertEqual(open_url.call_count, 2)
        self.assertEqual(translated, "अनुवाद अनुवाद")
        query = parse_qs(urlparse(open_url.call_args.args[0].full_url).query)
        self.assertEqual(query["langpair"], ["en|kn"])
        self.assertLessEqual(len(query["q"][0]), 500)

    def test_google_fallback_handles_remaining_chunks_after_mymemory_failure(self):
        class GoogleResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps([[ ["नमस्ते", "Hello", None, None, 1] ], None, "en"]).encode("utf-8")

        source = "word " * 104
        with patch.object(
            app,
            "urlopen",
            side_effect=[OSError("MyMemory unavailable"), GoogleResponse(), GoogleResponse()],
        ) as open_url:
            translated = app.translate_with_provider(source, "en", "hi")

        self.assertEqual(translated, "नमस्ते नमस्ते")
        self.assertEqual(open_url.call_count, 3)
        self.assertIn("api.mymemory.translated.net", open_url.call_args_list[0].args[0].full_url)
        for call in open_url.call_args_list[1:]:
            self.assertIn("translate.googleapis.com", call.args[0].full_url)
            query = parse_qs(urlparse(call.args[0].full_url).query)
            self.assertEqual(query["sl"], ["en"])
            self.assertEqual(query["tl"], ["hi"])


class GenerateLanguageTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_translates_source_into_selected_language(self):
        with (
            patch.object(app.processor, "detect_language", return_value="en"),
            patch.object(app.processor, "validate_telugu_text", return_value={"valid": True}),
            patch.object(app, "translate_with_provider", return_value="अनूदित अध्ययन सामग्री") as translate,
            patch.object(app.processor, "generate_qa_pairs", return_value=[
                {"question": "प्रश्न", "answer": "उत्तर"},
            ]) as generate,
            patch.object(app, "GOOGLE_API_KEY", ""),
        ):
            response = await app.generate_qa(
                app.TextInput(text="English source study material.", language="hi"),
                username="test-user",
            )

        self.assertTrue(response.success)
        translate.assert_called_once_with("English source study material.", "en", "hi")
        generate.assert_called_once_with("अनूदित अध्ययन सामग्री", "hi")


if __name__ == "__main__":
    unittest.main()

import json
import unittest

from scripts.send_lark_cli_text import build_ascii_content


class LarkCliEncodingTests(unittest.TestCase):
    def test_build_ascii_content_escapes_chinese_for_windows_cli(self):
        content = build_ascii_content("论文 + 英语")

        content.encode("ascii")
        self.assertIn("\\u8bba\\u6587", content)
        self.assertIn("\\u82f1\\u8bed", content)
        self.assertEqual(json.loads(content), {"text": "论文 + 英语"})


if __name__ == "__main__":
    unittest.main()

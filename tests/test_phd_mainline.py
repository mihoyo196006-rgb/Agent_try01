from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from build_phd_mainline import build_summary


class PhdMainlineTests(unittest.TestCase):
    def test_build_summary_counts_signals_without_uploading_source_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("论文 理论 机制\n英语 雅思 写作\n", encoding="utf-8")
            (root / "00_申请总控.md").write_text("论文 变量\n", encoding="utf-8")

            summary = build_summary(root, now=datetime(2026, 6, 16, 23, 0, tzinfo=timezone.utc))

            self.assertEqual(summary["mainlines"], ["论文", "英语"])
            self.assertGreaterEqual(summary["paper"]["signal_count"], 4)
            self.assertGreaterEqual(summary["english"]["signal_count"], 3)
            self.assertIn("sources", summary)
            dumped = str(summary)
            self.assertNotIn("理论 机制", dumped)
            self.assertNotIn("雅思 写作", dumped)


if __name__ == "__main__":
    unittest.main()

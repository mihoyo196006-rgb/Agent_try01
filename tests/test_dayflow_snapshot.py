from datetime import datetime
import unittest

from read_dayflow_state import build_compact_snapshot, classify_domain


class DayflowSnapshotTests(unittest.TestCase):
    def test_build_compact_snapshot_keeps_only_compact_fields(self):
        tasks = [
            {
                "title": "修改论文引言",
                "time": "",
                "date": "2026-06-16",
                "dateEnd": "2026-06-16",
                "list": "today",
                "domain": "",
                "priority": "high",
                "done": True,
                "deleted": False,
                "note": "a long note that should not be copied",
                "updatedAt": "2026-06-16T20:00:00.000Z",
            },
            {
                "title": "英语复述训练",
                "time": "",
                "date": "2026-06-16",
                "dateEnd": "2026-06-16",
                "list": "today",
                "domain": "",
                "priority": "medium",
                "done": False,
                "deleted": False,
                "note": "",
                "updatedAt": "2026-06-16T21:00:00.000Z",
            },
        ]

        snapshot = build_compact_snapshot(
            tasks,
            target_date="2026-06-16",
            captured_at=datetime(2026, 6, 16, 23, 50),
            capture_kind="main",
            source_status="ok",
            source_file="state.ldb",
        )

        self.assertEqual(snapshot["snapshot_date"], "2026-06-16")
        self.assertEqual(snapshot["capture_kind"], "main")
        self.assertEqual(snapshot["counts"], {"total": 2, "done": 1, "open": 1})
        self.assertEqual(snapshot["done_tasks"], [{"title": "论文任务", "domain": "paper", "priority": "high"}])
        self.assertEqual(snapshot["open_tasks"], [{"title": "英语任务", "domain": "english", "priority": "medium"}])
        self.assertNotIn("note", snapshot["done_tasks"][0])

    def test_build_compact_snapshot_can_keep_titles_when_explicitly_requested(self):
        tasks = [
            {
                "title": "修改论文引言",
                "date": "2026-06-16",
                "dateEnd": "2026-06-16",
                "list": "today",
                "domain": "",
                "priority": "high",
                "done": True,
                "deleted": False,
            }
        ]

        snapshot = build_compact_snapshot(
            tasks,
            target_date="2026-06-16",
            captured_at=datetime(2026, 6, 16, 23, 50),
            capture_kind="main",
            source_status="ok",
            source_file="state.ldb",
            redact_titles=False,
        )

        self.assertEqual(snapshot["done_tasks"][0]["title"], "修改论文引言")

    def test_classify_domain_falls_back_to_other(self):
        self.assertEqual(classify_domain("修改论文引言", ""), "paper")
        self.assertEqual(classify_domain("雅思听力训练", ""), "english")
        self.assertEqual(classify_domain("买牛奶", ""), "other")

    def test_supplement_snapshot_does_not_treat_new_today_as_yesterday(self):
        tasks = [
            {
                "title": "新一天英语任务",
                "date": "",
                "dateEnd": "",
                "list": "today",
                "domain": "",
                "priority": "medium",
                "done": False,
                "deleted": False,
                "updatedAt": "2026-06-17T00:05:00.000+08:00",
            }
        ]

        snapshot = build_compact_snapshot(
            tasks,
            target_date="2026-06-16",
            captured_at=datetime(2026, 6, 17, 0, 10),
            capture_kind="supplement",
            source_status="ok",
            source_file="state.ldb",
        )

        self.assertEqual(snapshot["counts"], {"total": 0, "done": 0, "open": 0})
        self.assertEqual(snapshot["open_tasks"], [])


if __name__ == "__main__":
    unittest.main()

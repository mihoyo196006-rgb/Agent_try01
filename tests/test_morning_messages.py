from datetime import datetime, timezone
import json
import unittest

from send_morning_plan import build_messages, load_best_snapshot


class MorningMessageTests(unittest.TestCase):
    def test_build_messages_returns_yesterday_summary_and_today_plan(self):
        snapshot = {
            "snapshot_date": "2026-06-16",
            "captured_at": "2026-06-16T23:50:00+08:00",
            "source_status": "ok",
            "counts": {"total": 3, "done": 2, "open": 1},
            "done_tasks": [
                {"title": "修改论文引言", "domain": "paper", "priority": "high"},
                {"title": "整理英语表达", "domain": "english", "priority": "medium"},
            ],
            "open_tasks": [{"title": "继续论文机制图", "domain": "paper", "priority": "medium"}],
        }
        phd = {
            "mainlines": ["论文", "英语"],
            "paper": {"current_focus": "论文修改与理论机制梳理"},
            "english": {"current_focus": "博士申请相关英语能力准备"},
        }

        messages = build_messages(snapshot, phd, now=datetime(2026, 6, 17, 1, 30, tzinfo=timezone.utc))

        self.assertEqual(len(messages), 2)
        self.assertTrue(messages[0].startswith("📌 昨日总结｜2026-06-16"))
        self.assertIn("✅ 完成情况", messages[0])
        self.assertIn("🎯 对主线的帮助", messages[0])
        self.assertIn("━━━━━━━━━━━━", messages[0])
        self.assertIn("修改论文引言", messages[0])
        self.assertIn("论文任务完成 1 项", messages[0])
        self.assertIn("英语任务完成 1 项", messages[0])
        self.assertTrue(messages[1].startswith("📌 今日规划｜2026-06-17"))
        self.assertIn("🧭 今日主线", messages[1])
        self.assertIn("🗓️ 时间安排", messages[1])
        self.assertIn("09:30-10:30 论文", messages[1])
        self.assertIn("英语", messages[1])
        self.assertNotIn("*", messages[0])
        self.assertNotIn("*", messages[1])
        self.assertNotIn("材料", messages[1])
        self.assertNotIn("导师", messages[1])
        self.assertNotIn("行政", messages[1])
        self.assertNotIn("缓冲", messages[1])

    def test_build_messages_marks_stale_snapshot(self):
        snapshot = {
            "snapshot_date": "2026-06-14",
            "captured_at": "2026-06-14T23:50:00+08:00",
            "source_status": "ok",
            "counts": {"total": 1, "done": 1, "open": 0},
            "done_tasks": [{"title": "旧任务", "domain": "paper", "priority": "low"}],
            "open_tasks": [],
        }
        phd = {"mainlines": ["论文", "英语"], "paper": {}, "english": {}}

        messages = build_messages(snapshot, phd, now=datetime(2026, 6, 17, 1, 30, tzinfo=timezone.utc))

        self.assertIn("未收到昨晚 Dayflow 新快照", messages[0])
        self.assertIn("未收到昨晚 Dayflow 新快照", messages[1])

    def test_load_best_snapshot_prefers_yesterday_main_over_empty_supplement(self):
        class FakePath:
            def __init__(self, files):
                self.files = files

            def __truediv__(self, child):
                return FakePathFile(self.files, child)

        class FakePathFile:
            def __init__(self, files, name):
                self.files = files
                self.name = name

            def exists(self):
                return self.name in self.files

            def read_text(self, encoding):
                return self.files[self.name]

        files = {
            "2026-06-16-2350.json": json.dumps(
                {
                    "snapshot_date": "2026-06-16",
                    "capture_kind": "main",
                    "counts": {"total": 2, "done": 1, "open": 1},
                }
            ),
            "2026-06-16-0010.json": json.dumps(
                {
                    "snapshot_date": "2026-06-16",
                    "capture_kind": "supplement",
                    "counts": {"total": 0, "done": 0, "open": 0},
                }
            ),
            "latest.json": json.dumps({"snapshot_date": "2026-06-17", "capture_kind": "manual"}),
        }

        snapshot = load_best_snapshot(FakePath(files), now=datetime(2026, 6, 17, 1, 30, tzinfo=timezone.utc))

        self.assertEqual(snapshot["capture_kind"], "main")
        self.assertEqual(snapshot["counts"]["total"], 2)


if __name__ == "__main__":
    unittest.main()

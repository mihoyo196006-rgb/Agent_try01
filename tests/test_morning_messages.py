from datetime import datetime, timezone
import io
import json
import os
import unittest
from unittest.mock import patch

from send_morning_plan import (
    build_delivery_marker,
    build_message_url,
    build_message_uuids,
    build_messages,
    is_beijing_send_window,
    load_best_snapshot,
    load_cloud_snapshot,
    load_inputs,
)


class MorningMessageTests(unittest.TestCase):
    def test_build_messages_returns_yesterday_summary_and_today_plan(self):
        snapshot = {
            "snapshot_date": "2026-06-16",
            "captured_at": "2026-06-16T23:50:00+08:00",
            "source_status": "ok",
            "capture_kind": "main",
            "source_modified_at": "2026-06-16T23:49:41+08:00",
            "freshness": {"cache_age_minutes": 1},
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

        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0].startswith("🧾 昨日总结｜2026-06-16"))
        self.assertIn("🧾 昨日总结｜2026-06-16", messages[0])
        self.assertIn("✅ Dayflow", messages[0])
        self.assertIn("🎯 对主线的帮助", messages[0])
        self.assertNotIn("  共计：3 项", messages[0])
        self.assertNotIn("  完成：2 项", messages[0])
        self.assertNotIn("  未完成：1 项", messages[0])
        self.assertNotIn("Dayflow：共 3 项｜完成 2 项｜未完成 1 项", messages[0])
        self.assertIn("  已完成：", messages[0])
        self.assertIn("  - 论文：1 项", messages[0])
        self.assertIn("  - 英语：1 项", messages[0])
        self.assertNotIn("修改论文引言", messages[0])
        self.assertIn("论文任务完成 1 项", messages[0])
        self.assertIn("英语任务完成 1 项", messages[0])
        self.assertNotIn("📌 早晨提醒", messages[0])
        self.assertNotIn("⏰ 时间定位", messages[0])
        self.assertNotIn("📍 数据状态", messages[0])
        self.assertNotIn("🔁 昨日未完成", messages[0])
        self.assertNotIn("📝 今日任务", messages[0])
        self.assertNotIn("请你自己制定", messages[0])
        self.assertNotIn("今日规划", messages[0])
        self.assertNotIn("09:30-10:30", messages[0])
        self.assertNotIn("【格式测试】", messages[0])
        self.assertNotIn("*", messages[0])
        self.assertNotIn("材料", messages[0])
        self.assertNotIn("导师", messages[0])
        self.assertNotIn("行政", messages[0])
        self.assertNotIn("缓冲", messages[0])

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

    def test_load_best_snapshot_uses_yesterday_main_snapshot_only(self):
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
                    "counts": {"total": 9, "done": 9, "open": 0},
                }
            ),
            "latest.json": json.dumps({"snapshot_date": "2026-06-17", "capture_kind": "manual"}),
        }

        snapshot = load_best_snapshot(FakePath(files), now=datetime(2026, 6, 17, 1, 30, tzinfo=timezone.utc))

        self.assertEqual(snapshot["capture_kind"], "main")
        self.assertEqual(snapshot["counts"]["total"], 2)

    def test_load_best_snapshot_ignores_old_supplement_without_main_snapshot(self):
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
            "2026-06-16-0010.json": json.dumps(
                {
                    "snapshot_date": "2026-06-16",
                    "capture_kind": "supplement",
                    "counts": {"total": 9, "done": 9, "open": 0},
                }
            ),
            "latest.json": json.dumps({"snapshot_date": "2026-06-17", "capture_kind": "manual"}),
        }

        snapshot = load_best_snapshot(FakePath(files), now=datetime(2026, 6, 17, 1, 30, tzinfo=timezone.utc))

        self.assertEqual(snapshot["source_status"], "missing")
        self.assertEqual(snapshot["counts"]["total"], 0)

    def test_load_cloud_snapshot_uses_bearer_token(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "snapshot_date": "2026-06-16",
                        "source_status": "ok",
                        "counts": {"total": 1, "done": 1, "open": 0},
                        "done_tasks": [{"title": "论文任务", "domain": "paper", "priority": "high"}],
                        "open_tasks": [],
                    }
                ).encode("utf-8")

        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen):
            snapshot = load_cloud_snapshot("https://example.worker.dev/dayflow/current", "read-token", "2026-06-16")

        self.assertEqual(snapshot["source_status"], "ok")
        self.assertEqual(snapshot["snapshot_date"], "2026-06-16")
        self.assertEqual(captured["url"], "https://example.worker.dev/dayflow/current?date=2026-06-16")
        self.assertEqual(captured["auth"], "Bearer read-token")
        self.assertEqual(captured["timeout"], 30)

    def test_load_inputs_prefers_cloud_snapshot_when_configured(self):
        cloud_snapshot = {
            "snapshot_date": "2026-06-16",
            "source_status": "ok",
            "counts": {"total": 1, "done": 1, "open": 0},
            "done_tasks": [{"title": "论文任务", "domain": "paper", "priority": "high"}],
            "open_tasks": [],
        }

        with patch.dict(
            os.environ,
            {
                "DAYFLOW_CLOUD_ENDPOINT": "https://example.worker.dev/dayflow/current",
                "DAYFLOW_READ_TOKEN": "read-token",
            },
            clear=False,
        ), patch("send_morning_plan.load_cloud_snapshot", return_value=cloud_snapshot):
            snapshot, phd = load_inputs()

        self.assertEqual(snapshot, cloud_snapshot)
        self.assertIn("mainlines", phd)

    def test_load_inputs_uses_manual_target_date_when_configured(self):
        cloud_snapshot = {
            "snapshot_date": "2026-06-24",
            "source_status": "ok",
            "counts": {"total": 7, "done": 6, "open": 1},
            "done_tasks": [],
            "open_tasks": [],
        }
        captured = {}

        def fake_load_cloud_snapshot(endpoint, token, target_date):
            captured["target_date"] = target_date
            return cloud_snapshot

        with patch.dict(
            os.environ,
            {
                "DAYFLOW_CLOUD_ENDPOINT": "https://example.worker.dev/dayflow/current",
                "DAYFLOW_READ_TOKEN": "read-token",
                "DAYFLOW_TARGET_DATE": "2026-06-24",
            },
            clear=False,
        ), patch("send_morning_plan.load_cloud_snapshot", fake_load_cloud_snapshot):
            snapshot, _phd = load_inputs()

        self.assertEqual(snapshot, cloud_snapshot)
        self.assertEqual(captured["target_date"], "2026-06-24")

    def test_beijing_send_window_accepts_only_morning_calibration_window(self):
        self.assertTrue(is_beijing_send_window(datetime(2026, 6, 17, 1, 30, tzinfo=timezone.utc)))
        self.assertTrue(is_beijing_send_window(datetime(2026, 6, 17, 1, 50, tzinfo=timezone.utc)))
        self.assertTrue(is_beijing_send_window(datetime(2026, 6, 17, 2, 0, 4, tzinfo=timezone.utc)))
        self.assertTrue(is_beijing_send_window(datetime(2026, 6, 17, 2, 15, tzinfo=timezone.utc)))
        self.assertTrue(is_beijing_send_window(datetime(2026, 6, 17, 2, 30, tzinfo=timezone.utc)))
        self.assertFalse(is_beijing_send_window(datetime(2026, 6, 17, 1, 29, 59, tzinfo=timezone.utc)))
        self.assertFalse(is_beijing_send_window(datetime(2026, 6, 17, 1, 10, tzinfo=timezone.utc)))
        self.assertFalse(is_beijing_send_window(datetime(2026, 6, 17, 2, 31, tzinfo=timezone.utc)))

    def test_message_uuids_are_stable_per_beijing_date_and_message_index(self):
        uuids = build_message_uuids(datetime(2026, 6, 17, 1, 30, tzinfo=timezone.utc), 2)

        self.assertEqual(uuids, ["morning-feishu-2026-06-17-1", "morning-feishu-2026-06-17-2"])
        self.assertLessEqual(max(len(value) for value in uuids), 64)

    def test_message_uuids_can_include_manual_suffix(self):
        with patch.dict(os.environ, {"MESSAGE_UUID_SUFFIX": "28111084745"}, clear=False):
            uuids = build_message_uuids(datetime(2026, 6, 17, 1, 30, tzinfo=timezone.utc), 1)

        self.assertEqual(uuids, ["morning-feishu-2026-06-17-1-28111084745"])
        self.assertLessEqual(len(uuids[0]), 64)

    def test_build_message_url_adds_uuid_when_present(self):
        url = build_message_url("morning-feishu-2026-06-17-1")

        self.assertEqual(
            url,
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id&uuid=morning-feishu-2026-06-17-1",
        )

    def test_build_delivery_marker_records_successful_send(self):
        snapshot = {
            "snapshot_date": "2026-06-16",
            "capture_kind": "main",
            "counts": {"total": 3, "done": 2, "open": 1},
            "source_file": "010577.log",
            "source_modified_at": "2026-06-16T23:49:41+08:00",
        }
        results = [
            {"code": 0, "data": {"message_id": "om_1"}},
            {"code": 0, "data": {"message_id": "om_2"}},
        ]

        marker = build_delivery_marker(
            snapshot,
            results,
            now=datetime(2026, 6, 17, 2, 0, 4, tzinfo=timezone.utc),
        )

        self.assertEqual(marker["date"], "2026-06-17")
        self.assertEqual(marker["sent_at_beijing"], "2026-06-17T10:00:04+08:00")
        self.assertEqual(marker["snapshot_date"], "2026-06-16")
        self.assertEqual(marker["counts"], {"total": 3, "done": 2, "open": 1})
        self.assertEqual(marker["message_ids"], ["om_1", "om_2"])
        self.assertEqual(marker["status"], "sent")


if __name__ == "__main__":
    unittest.main()

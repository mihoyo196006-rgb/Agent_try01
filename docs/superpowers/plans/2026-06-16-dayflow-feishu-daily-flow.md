# Dayflow Feishu Daily Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local Dayflow snapshot push flow and the cloud 09:30 two-message Feishu sender.

**Architecture:** Local Windows scheduled jobs write compact Dayflow and PhD JSON summaries into `data/`, then commit and push them. GitHub Actions runs at Beijing 09:30, reads those summaries, generates two deterministic zero-token messages, and sends them via the existing Feishu bot API.

**Tech Stack:** Python 3.12 standard library, pytest, GitHub Actions, Windows Task Scheduler, Feishu Open API.

---

### Task 1: Add Message Generation Tests

**Files:**
- Create: `tests/test_morning_messages.py`
- Modify later: `send_morning_plan.py`

- [ ] **Step 1: Write failing tests**

Create tests that define the expected API:

```python
from datetime import datetime, timezone

from send_morning_plan import build_messages


def test_build_messages_returns_yesterday_summary_and_today_plan():
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

    assert len(messages) == 2
    assert messages[0].startswith("昨日总结｜2026-06-16")
    assert "完成情况：" in messages[0]
    assert "对主线的帮助：" in messages[0]
    assert "修改论文引言" in messages[0]
    assert messages[1].startswith("今日规划｜2026-06-17")
    assert "09:30-10:30 论文" in messages[1]
    assert "英语" in messages[1]
    assert "材料" not in messages[1]
    assert "导师" not in messages[1]
    assert "行政" not in messages[1]
    assert "缓冲" not in messages[1]


def test_build_messages_marks_stale_snapshot():
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

    assert "未收到昨晚 Dayflow 新快照" in messages[0]
    assert "未收到昨晚 Dayflow 新快照" in messages[1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_morning_messages -v`

Expected: FAIL because `build_messages` does not exist.

- [ ] **Step 3: Implement minimal message generator**

Modify `send_morning_plan.py` to define `build_messages(snapshot, phd, now=None)` and update `main()` to send both messages.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_morning_messages -v`

Expected: PASS.

### Task 2: Add Snapshot Writer Tests

**Files:**
- Create: `tests/test_dayflow_snapshot.py`
- Modify later: `read_dayflow_state.py`

- [ ] **Step 1: Write failing tests**

```python
from datetime import datetime

from read_dayflow_state import build_compact_snapshot, classify_domain


def test_build_compact_snapshot_keeps_only_compact_fields():
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

    assert snapshot["snapshot_date"] == "2026-06-16"
    assert snapshot["capture_kind"] == "main"
    assert snapshot["counts"] == {"total": 2, "done": 1, "open": 1}
    assert snapshot["done_tasks"] == [{"title": "修改论文引言", "domain": "paper", "priority": "high"}]
    assert snapshot["open_tasks"] == [{"title": "英语复述训练", "domain": "english", "priority": "medium"}]
    assert "note" not in snapshot["done_tasks"][0]


def test_classify_domain_falls_back_to_other():
    assert classify_domain("修改论文引言", "") == "paper"
    assert classify_domain("雅思听力训练", "") == "english"
    assert classify_domain("买牛奶", "") == "other"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_dayflow_snapshot -v`

Expected: FAIL because `build_compact_snapshot` and `classify_domain` do not exist.

- [ ] **Step 3: Implement snapshot compaction**

Modify `read_dayflow_state.py` to add compaction, file writing, and CLI arguments:

- `--capture-kind main|supplement|manual`
- `--target-date YYYY-MM-DD`
- `--out-dir data/dayflow`
- `--write`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_dayflow_snapshot -v`

Expected: PASS.

### Task 3: Add PhD Summary and Local Push Script

**Files:**
- Create: `data/phd/mainline.json`
- Create: `scripts/local_snapshot_and_push.ps1`

- [ ] **Step 1: Write compact PhD mainline JSON**

Create `data/phd/mainline.json` with 论文 and 英语 as the only default mainlines.

- [ ] **Step 2: Create local push script**

Create `scripts/local_snapshot_and_push.ps1` that runs `read_dayflow_state.py --write`, stages `data/dayflow/*.json` and `data/phd/mainline.json`, commits only when there are changes, and pushes to `origin main`.

- [ ] **Step 3: Run script in manual mode**

Run: `powershell -ExecutionPolicy Bypass -File scripts/local_snapshot_and_push.ps1 -CaptureKind manual`

Expected: writes compact JSON and either commits/pushes changes or reports no changes.

### Task 4: Update Cloud Sender Workflow

**Files:**
- Modify: `.github/workflows/morning-feishu.yml`
- Modify: `send_morning_plan.py`

- [ ] **Step 1: Update schedule**

Change cron from `0 1 * * *` to `30 1 * * *`.

- [ ] **Step 2: Send two messages**

Ensure `send_morning_plan.py` loads `data/dayflow/latest.json`, loads `data/phd/mainline.json`, builds two messages, and sends both.

- [ ] **Step 3: Run unit tests**

Run: `python -m unittest discover -s tests -v`

Expected: PASS.

### Task 5: Register Windows Scheduled Tasks

**Files:**
- Create: `scripts/register_windows_tasks.ps1`

- [ ] **Step 1: Create registration script**

Create a PowerShell script that registers:

- `DayflowFeishuSnapshot2350` at 23:50 with `-CaptureKind main`
- `DayflowFeishuSnapshot0010` at 00:10 with `-CaptureKind supplement`

- [ ] **Step 2: Register tasks**

Run: `powershell -ExecutionPolicy Bypass -File scripts/register_windows_tasks.ps1`

Expected: both scheduled tasks exist and point at `scripts/local_snapshot_and_push.ps1`.

### Task 6: Final Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run all tests**

Run: `python -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 2: Run syntax checks**

Run: `python -m py_compile send_morning_plan.py read_dayflow_state.py`

Expected: no output and exit code 0.

- [ ] **Step 3: Inspect git diff**

Run: `git status --short` and `git diff --stat`

Expected: only intended files changed, with no `__pycache__/` staged.

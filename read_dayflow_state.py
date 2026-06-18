from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


LEVELDB_DIR = Path.home() / "AppData" / "Roaming" / "daily-task-widget" / "Local Storage" / "leveldb"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "data" / "dayflow"
KEY = b"daily-task-app-state-v5"
UTF16_JSON_PREFIX = "{\"version\":5".encode("utf-16le")


TASK_PATTERN = re.compile(
    r'\{"id":"(?P<id>[^"]+)","title":"(?P<title>(?:\\.|[^"])*)","note":"(?P<note>(?:\\.|[^"])*)",'
    r'"time":"(?P<time>[^"]*)","date":"(?P<date>[^"]*)","dateEnd":"(?P<dateEnd>[^"]*)","list":"(?P<list>[^"]*)",'
    r'"domain":"(?P<domain>[^"]*)","order":(?P<order>\d+),"dayPartOverride":"(?P<dayPartOverride>[^"]*)",'
    r'"priority":"(?P<priority>[^"]*)","done":(?P<done>true|false),"completedDates":\{.*?\},"occurrenceOverrides":\{.*?\},'
    r'"deleted":(?P<deleted>true|false),"createdAt":(?P<createdAt>\d+),"updatedAt":"(?P<updatedAt>[^"]+)",'
    r'"completedAt":(?P<completedAt>null|"[^"]*"),"deletedAt":(?P<deletedAt>null|"[^"]*")\}',
    re.S,
)


def load_latest_text() -> tuple[Path, str]:
    files = sorted(
        list(LEVELDB_DIR.glob("*.log")) + list(LEVELDB_DIR.glob("*.ldb")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files:
        data = path.read_bytes()
        idx = data.rfind(KEY)
        if idx == -1:
            continue
        rel = data[idx : idx + 400].find(UTF16_JSON_PREFIX)
        if rel == -1:
            continue
        start = idx + rel
        text = data[start:].decode("utf-16le", errors="ignore")
        if TASK_PATTERN.search(text):
            return path, text
    raise FileNotFoundError("DayFlow state key not found in LevelDB logs.")


def parse_tasks(text: str) -> list[dict]:
    tasks: list[dict] = []
    for match in TASK_PATTERN.finditer(text):
        task = match.groupdict()
        task["title"] = json.loads(f'"{task["title"].replace("\"", "\\\"")}"')
        task["note"] = json.loads(f'"{task["note"].replace("\"", "\\\"")}"')
        task["done"] = task["done"] == "true"
        task["deleted"] = task["deleted"] == "true"
        tasks.append(task)
    return tasks


def infer_occurs_today(task: dict, today: str) -> bool:
    date = task.get("date") or ""
    date_end = task.get("dateEnd") or ""
    return bool(date and date <= today and (date_end or date) >= today)


def classify_domain(title: str, existing_domain: str = "") -> str:
    normalized = f"{existing_domain} {title}".lower()
    if any(keyword in normalized for keyword in ["论文", "文章", "引言", "理论", "机制", "文献", "变量", "结果", "paper"]):
        return "paper"
    if any(keyword in normalized for keyword in ["英语", "雅思", "ielts", "english", "口语", "听力", "阅读", "写作", "复述", "表达"]):
        return "english"
    return "other"


def task_occurs_on(task: dict, target_date: str, *, include_today_list: bool = True) -> bool:
    date = task.get("date") or ""
    date_end = task.get("dateEnd") or ""
    if include_today_list and task.get("list") == "today" and (not date or date == target_date):
        return True
    return bool(date and date <= target_date and (date_end or date) >= target_date)


def compact_task(task: dict, *, redact_titles: bool = True) -> dict:
    domain = classify_domain(task["title"], task.get("domain", ""))
    if redact_titles:
        title = {"paper": "论文任务", "english": "英语任务"}.get(domain, "其他任务")
    else:
        title = task["title"]
    return {
        "title": title,
        "domain": domain,
        "priority": task.get("priority", ""),
    }


def build_compact_snapshot(
    tasks: list[dict],
    *,
    target_date: str,
    captured_at: datetime,
    capture_kind: str,
    source_status: str,
    source_file: str = "",
    source_modified_at: datetime | None = None,
    error: str = "",
    redact_titles: bool = True,
) -> dict:
    include_today_list = capture_kind != "supplement"
    active = [
        task
        for task in tasks
        if not task.get("deleted") and task_occurs_on(task, target_date, include_today_list=include_today_list)
    ]
    done = [compact_task(task, redact_titles=redact_titles) for task in active if task.get("done")]
    open_tasks = [compact_task(task, redact_titles=redact_titles) for task in active if not task.get("done")]
    freshness = {
        "is_expected_window": capture_kind in {"main", "supplement"},
        "age_hours_at_commit": 0,
    }
    if source_modified_at:
        freshness["cache_age_minutes"] = max(0, int((captured_at - source_modified_at).total_seconds() // 60))

    snapshot = {
        "snapshot_date": target_date,
        "captured_at": captured_at.isoformat(),
        "capture_kind": capture_kind,
        "source_status": source_status,
        "source_file": source_file,
        "error": error,
        "freshness": freshness,
        "counts": {
            "total": len(active),
            "done": len(done),
            "open": len(open_tasks),
        },
        "done_tasks": done,
        "open_tasks": open_tasks,
    }
    if source_modified_at:
        snapshot["source_modified_at"] = source_modified_at.isoformat()
    return snapshot


def write_snapshot(snapshot: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    date_text = snapshot["snapshot_date"]
    suffix = {"main": "2350", "supplement": "0010"}.get(snapshot["capture_kind"], "manual")
    dated_path = out_dir / f"{date_text}-{suffix}.json"
    text = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    dated_path.write_text(text, encoding="utf-8")
    return [dated_path]


def beijing_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))


def default_target_date(capture_kind: str, now: datetime) -> str:
    if capture_kind == "supplement":
        return (now.date() - timedelta(days=1)).isoformat()
    if capture_kind == "main" and now.hour < 4:
        return (now.date() - timedelta(days=1)).isoformat()
    return now.date().isoformat()


def summarize(tasks: list[dict]) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    active_today = []
    inbox_open = []
    recent_open = []

    for task in tasks:
        if task["deleted"]:
            continue
        if task["list"] == "today" or infer_occurs_today(task, today):
            active_today.append(task)
        if task["list"] == "inbox" and not task["done"]:
            inbox_open.append(task)
        if not task["done"] and task["updatedAt"].startswith(today[:8]):
            recent_open.append(task)

    def pick_fields(task: dict) -> dict:
        return {
            "title": task["title"],
            "time": task["time"],
            "date": task["date"],
            "dateEnd": task["dateEnd"],
            "list": task["list"],
            "domain": task["domain"],
            "dayPartOverride": task["dayPartOverride"],
            "priority": task["priority"],
            "done": task["done"],
            "updatedAt": task["updatedAt"],
            "note": task["note"],
        }

    return {
        "today": today,
        "source_status": "ok",
        "active_today_count": len(active_today),
        "active_today": [pick_fields(task) for task in active_today],
        "open_inbox_count": len(inbox_open),
        "open_inbox": [pick_fields(task) for task in inbox_open[:20]],
        "recent_open_count": len(recent_open),
        "recent_open": [pick_fields(task) for task in recent_open[:20]],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read Dayflow local state and optionally write compact snapshots.")
    parser.add_argument("--capture-kind", choices=["main", "supplement", "manual"], default="manual")
    parser.add_argument("--target-date", default="")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--include-task-titles", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = beijing_now()
    target_date = args.target_date or default_target_date(args.capture_kind, now)
    try:
        source, text = load_latest_text()
        tasks = parse_tasks(text)
        payload = build_compact_snapshot(
            tasks,
            target_date=target_date,
            captured_at=now,
            capture_kind=args.capture_kind,
            source_status="ok",
            source_file=source.name,
            source_modified_at=datetime.fromtimestamp(source.stat().st_mtime, tz=now.tzinfo),
            redact_titles=not args.include_task_titles,
        )
        payload["matched_tasks"] = len(tasks)
        if args.write:
            payload["written_files"] = [str(path) for path in write_snapshot(payload, args.out_dir)]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        payload = build_compact_snapshot(
            [],
            target_date=target_date,
            captured_at=now,
            capture_kind=args.capture_kind,
            source_status="error",
            source_file="",
            error=str(exc),
            redact_titles=True,
        )
        payload["source_dir"] = "local_dayflow_leveldb"
        if args.write:
            payload["written_files"] = [str(path) for path in write_snapshot(payload, args.out_dir)]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

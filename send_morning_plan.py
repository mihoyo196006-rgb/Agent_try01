import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request


DATA_DIR = Path(__file__).resolve().parent / "data"
DELIVERY_DIR = DATA_DIR / "delivery"
STALE_NOTICE = "未收到昨晚 Dayflow 新快照，以下基于最近一次快照和 PhD 主线生成。"
DIVIDER = "──────"
SEND_WINDOW_START = dt.time(9, 30)
SEND_WINDOW_END = dt.time(10, 30, 59)
DOMAIN_LABELS = {"paper": "论文", "english": "英语", "other": "其他"}


def beijing_now(now: dt.datetime | None = None) -> dt.datetime:
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    return current.astimezone(dt.timezone(dt.timedelta(hours=8)))


def is_beijing_send_window(now: dt.datetime | None = None) -> bool:
    current_time = beijing_now(now).time()
    return SEND_WINDOW_START <= current_time <= SEND_WINDOW_END


def expected_snapshot_date(now: dt.datetime | None = None) -> str:
    override = os.environ.get("DAYFLOW_TARGET_DATE", "").strip()
    if override:
        return override
    if os.environ.get("DAYFLOW_MANUAL_RUN", "").strip() == "1":
        return beijing_now(now).date().isoformat()
    return (beijing_now(now).date() - dt.timedelta(days=1)).isoformat()


def build_message_uuids(now: dt.datetime | None, count: int) -> list[str]:
    today = beijing_now(now).date().isoformat()
    suffix = os.environ.get("MESSAGE_UUID_SUFFIX", "").strip()
    if suffix:
        suffix = "-" + suffix[:24]
    return [f"morning-feishu-{today}-{index}{suffix}" for index in range(1, count + 1)]


def build_message_url(message_uuid: str | None = None) -> str:
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    if message_uuid:
        url += "&uuid=" + urllib.parse.quote(message_uuid, safe="")
    return url


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_best_snapshot(dayflow_dir: Path, now: dt.datetime | None = None) -> dict:
    expected_date = (beijing_now(now).date() - dt.timedelta(days=1)).isoformat()
    default = {
        "snapshot_date": "",
        "source_status": "missing",
        "counts": {"total": 0, "done": 0, "open": 0},
        "done_tasks": [],
        "open_tasks": [],
    }
    path = dayflow_dir / f"{expected_date}-2350.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def load_cloud_snapshot(endpoint: str, token: str | None = None, target_date: str | None = None) -> dict:
    if target_date:
        separator = "&" if "?" in endpoint else "?"
        endpoint = f"{endpoint}{separator}date={urllib.parse.quote(target_date, safe='')}"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(endpoint, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(body)
        snapshot = json.loads(body) if body else {}
    if not isinstance(snapshot, dict):
        raise RuntimeError("Dayflow cloud endpoint returned a non-object payload.")
    return snapshot


def is_fresh_snapshot(snapshot: dict, now: dt.datetime | None = None) -> bool:
    if snapshot.get("source_status") != "ok":
        return False
    return snapshot.get("snapshot_date") == expected_snapshot_date(now)


def aggregate_domains(tasks: list[dict]) -> dict[str, int]:
    counts = {"paper": 0, "english": 0, "other": 0}
    for task in tasks:
        domain = task.get("domain") if task.get("domain") in counts else "other"
        counts[domain] += 1
    return {domain: count for domain, count in counts.items() if count}


def domain_summary_lines(tasks: list[dict], empty_text: str) -> list[str]:
    counts = aggregate_domains(tasks)
    if not counts:
        return [f"  - {empty_text}"]
    return [f"  - {DOMAIN_LABELS[domain]}：{count} 项" for domain, count in counts.items()]


def infer_mainline_help(done_tasks: list[dict], phd: dict) -> str:
    domains = {task.get("domain") for task in done_tasks}
    paper_done = sum(1 for task in done_tasks if task.get("domain") == "paper")
    english_done = sum(1 for task in done_tasks if task.get("domain") == "english")
    paper_focus = phd.get("paper", {}).get("current_focus") or "论文修改与理论机制梳理"
    english_focus = phd.get("english", {}).get("current_focus") or "英语输入、输出与表达积累"
    paper_signal = phd.get("paper", {}).get("signal_count")
    english_signal = phd.get("english", {}).get("signal_count")
    parts = []
    if "paper" in domains:
        signal_text = f"；当前 PhD 摘要中论文信号 {paper_signal} 条" if isinstance(paper_signal, int) else ""
        parts.append(f"论文任务完成 {paper_done} 项，推进了{paper_focus}{signal_text}。")
    if "english" in domains:
        signal_text = f"；当前 PhD 摘要中英语信号 {english_signal} 条" if isinstance(english_signal, int) else ""
        parts.append(f"英语任务完成 {english_done} 项，支持了{english_focus}{signal_text}。")
    if not parts:
        parts.append("昨天完成的任务没有明显落在论文或英语标签上；今天制定任务时可以主动压回论文和英语。")
    return "".join(parts)


def build_messages(snapshot: dict, phd: dict, now: dt.datetime | None = None) -> list[str]:
    bj_now = beijing_now(now)
    yesterday = snapshot.get("snapshot_date") or (bj_now.date() - dt.timedelta(days=1)).isoformat()
    counts = snapshot.get("counts", {})
    done_tasks = snapshot.get("done_tasks", [])
    stale_prefix = f"{STALE_NOTICE}\n\n" if not is_fresh_snapshot(snapshot, now) else ""

    summary = "\n".join(
        [
            *(["⚠️ 数据提醒", f"  {STALE_NOTICE}", ""] if stale_prefix else []),
            f"🧾 昨日总结｜{yesterday}",
            "",
            "✅ Dayflow",
            "  已完成：",
            *domain_summary_lines(done_tasks, "暂无记录"),
            "",
            "🎯 对主线的帮助",
            f"  {infer_mainline_help(done_tasks, phd)}",
        ]
    )
    return [summary]


def build_delivery_marker(snapshot: dict, results: list[dict], now: dt.datetime | None = None) -> dict:
    bj_now = beijing_now(now)
    return {
        "date": bj_now.date().isoformat(),
        "sent_at_beijing": bj_now.isoformat(timespec="seconds"),
        "status": "sent",
        "snapshot_date": snapshot.get("snapshot_date", ""),
        "snapshot_capture_kind": snapshot.get("capture_kind", ""),
        "counts": snapshot.get("counts", {}),
        "source_file": snapshot.get("source_file", ""),
        "source_modified_at": snapshot.get("source_modified_at", ""),
        "message_ids": [str(result.get("data", {}).get("message_id", "")) for result in results],
    }


def write_delivery_marker(marker: dict, delivery_dir: Path = DELIVERY_DIR) -> Path:
    delivery_dir.mkdir(parents=True, exist_ok=True)
    path = delivery_dir / f"{marker['date']}.json"
    path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_inputs() -> tuple[dict, dict]:
    endpoint = os.environ.get("DAYFLOW_CLOUD_ENDPOINT", "").strip()
    token = os.environ.get("DAYFLOW_READ_TOKEN", "").strip()
    expected_date = expected_snapshot_date()
    if endpoint:
        try:
            snapshot = load_cloud_snapshot(endpoint, token or None, expected_date)
        except Exception as exc:
            print(f"Dayflow cloud snapshot unavailable; falling back to local snapshot: {exc}", file=sys.stderr)
            snapshot = load_best_snapshot(DATA_DIR / "dayflow")
    else:
        snapshot = load_best_snapshot(DATA_DIR / "dayflow")
    phd = load_json(
        DATA_DIR / "phd" / "mainline.json",
        {"mainlines": ["论文", "英语"], "paper": {}, "english": {}},
    )
    return snapshot, phd


def post_json(url: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        result = json.loads(body) if body else {}
        if response.status >= 400:
            raise RuntimeError(body)
        return result


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    result = post_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    if result.get("code") != 0:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result["tenant_access_token"]


def send_text(token: str, user_id: str, text: str, message_uuid: str | None = None) -> dict:
    return post_json(
        build_message_url(message_uuid),
        {
            "receive_id": user_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        token=token,
    )


def main() -> int:
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    user_id = os.environ.get("FEISHU_USER_ID", "").strip()
    if not app_id or not app_secret or not user_id:
        print("Missing FEISHU_APP_ID, FEISHU_APP_SECRET, or FEISHU_USER_ID", file=sys.stderr)
        return 2

    try:
        now = dt.datetime.now(dt.timezone.utc)
        bj_now = beijing_now(now)
        print(f"UTC now: {now.isoformat()}")
        print(f"Beijing now: {bj_now.isoformat()}")
        print(f"GitHub event: {os.environ.get('GITHUB_EVENT_NAME', '')}")
        print(f"GitHub sha: {os.environ.get('GITHUB_SHA', '')}")
        if os.environ.get("REQUIRE_BEIJING_SEND_WINDOW", "").strip() == "1" and not is_beijing_send_window(now):
            print("Outside Beijing send window; skip Feishu delivery for calibration run.")
            return 0

        token = get_tenant_access_token(app_id, app_secret)
        snapshot, phd = load_inputs()
        messages = build_messages(snapshot, phd, now=now)
        uuids = build_message_uuids(now, len(messages))
        results = [send_text(token, user_id, message, message_uuid) for message, message_uuid in zip(messages, uuids)]
        print(json.dumps(results, ensure_ascii=False))
        if all(result.get("code") == 0 for result in results):
            marker_path = write_delivery_marker(build_delivery_marker(snapshot, results, now=now))
            print(f"Delivery marker: {marker_path}")
            return 0
        return 1
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

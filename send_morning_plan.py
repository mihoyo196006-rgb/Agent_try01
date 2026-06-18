import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request


DATA_DIR = Path(__file__).resolve().parent / "data"
STALE_NOTICE = "未收到昨晚 Dayflow 新快照，以下基于最近一次快照和 PhD 主线生成。"
DIVIDER = "──────"
SEND_WINDOW_START = dt.time(9, 20)
SEND_WINDOW_END = dt.time(10, 15, 59)


def beijing_now(now: dt.datetime | None = None) -> dt.datetime:
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    return current.astimezone(dt.timezone(dt.timedelta(hours=8)))


def is_beijing_send_window(now: dt.datetime | None = None) -> bool:
    current_time = beijing_now(now).time()
    return SEND_WINDOW_START <= current_time <= SEND_WINDOW_END


def build_message_uuids(now: dt.datetime | None, count: int) -> list[str]:
    today = beijing_now(now).date().isoformat()
    return [f"morning-feishu-{today}-{index}" for index in range(1, count + 1)]


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
    for name in [f"{expected_date}-2350.json", f"{expected_date}-0010.json", "latest.json"]:
        path = dayflow_dir / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return default


def is_fresh_snapshot(snapshot: dict, now: dt.datetime | None = None) -> bool:
    if snapshot.get("source_status") != "ok":
        return False
    expected_date = (beijing_now(now).date() - dt.timedelta(days=1)).isoformat()
    return snapshot.get("snapshot_date") == expected_date


def task_titles(tasks: list[dict], empty_text: str) -> str:
    titles = [str(task.get("title", "")).strip() for task in tasks if str(task.get("title", "")).strip()]
    return "；".join(titles) if titles else empty_text


def numbered_titles(tasks: list[dict], empty_text: str) -> list[str]:
    titles = [str(task.get("title", "")).strip() for task in tasks if str(task.get("title", "")).strip()]
    if not titles:
        return [f"  - {empty_text}"]
    return [f"  {index}. {title}" for index, title in enumerate(titles, 1)]


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
        parts.append("今天完成的任务没有明显落在论文或英语标签上，明天规划会重新压回这两条主线。")
    return "".join(parts)


def build_messages(snapshot: dict, phd: dict, now: dt.datetime | None = None) -> list[str]:
    bj_now = beijing_now(now)
    today = bj_now.date().isoformat()
    yesterday = snapshot.get("snapshot_date") or (bj_now.date() - dt.timedelta(days=1)).isoformat()
    counts = snapshot.get("counts", {})
    done_tasks = snapshot.get("done_tasks", [])
    open_tasks = snapshot.get("open_tasks", [])
    stale_prefix = f"{STALE_NOTICE}\n\n" if not is_fresh_snapshot(snapshot, now) else ""

    summary = "\n".join(
        [
            f"📌 昨日总结｜{yesterday}",
            DIVIDER,
            *(["⚠️ 数据提醒", f"  {STALE_NOTICE}", ""] if stale_prefix else []),
            "✅ 完成情况",
            f"  共计：{counts.get('total', 0)} 项",
            f"  完成：{counts.get('done', 0)} 项",
            f"  未完成：{counts.get('open', 0)} 项",
            "  已完成：",
            *numbered_titles(done_tasks, "暂无记录"),
            "",
            "🎯 对主线的帮助",
            f"  {infer_mainline_help(done_tasks, phd)}",
        ]
    )

    plan = "\n".join(
        [
            f"📌 今日规划｜{today}",
            DIVIDER,
            *(["⚠️ 数据提醒", f"  {STALE_NOTICE}", ""] if stale_prefix else []),
            "🧭 今日主线",
            "  论文：推进一处可交付修改",
            "  英语：完成一次输入或输出训练",
            "",
            "🗓️ 时间安排",
            "  09:30-10:30 论文｜确认今天要推进的一处修改，写出最小可交付段落",
            "  10:30-11:30 论文（文献阅读）｜补强理论机制或文献支撑",
            "  11:30-12:30 英语｜输入训练，记录可复用表达",
            "  14:00-15:00 英语（雅思）｜听力/阅读/写作择一推进",
            "  15:00-16:00 论文（文献阅读）｜围绕论文问题读一篇核心文献",
            "  16:00-17:00 论文（文献阅读）｜整理文献中的机制、变量或论证",
            "  17:00-18:00 论文｜整理今日改动，列出明天第一步",
            "  23:00-00:30 可选｜论文/文献阅读",
            "",
            "🔁 可回收任务",
            f"  {task_titles(open_tasks, '暂无')}",
        ]
    )
    return [summary, plan]


def load_inputs() -> tuple[dict, dict]:
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
        return 0 if all(result.get("code") == 0 for result in results) else 1
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

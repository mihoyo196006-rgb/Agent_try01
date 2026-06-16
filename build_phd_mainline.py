from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_PHD_DIR = Path("D:/PHD_application")
DEFAULT_OUT = Path(__file__).resolve().parent / "data" / "phd" / "mainline.json"
SELECTED_FILES = [
    "README.md",
    "00_申请总控.md",
    "06_六月执行计划.md",
    "07_每日进展记录.md",
    "09_英语准备_雅思碰一碰优化材料_简版.md",
]
PAPER_KEYWORDS = ["论文", "文章", "研究计划", "理论", "机制", "文献", "变量", "结果"]
ENGLISH_KEYWORDS = ["英语", "雅思", "听力", "阅读", "写作", "口语", "表达", "复述"]


def beijing_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))


def count_keywords(text: str, keywords: list[str]) -> int:
    return sum(text.count(keyword) for keyword in keywords)


def read_selected_sources(phd_dir: Path) -> tuple[list[dict], int, int]:
    sources = []
    paper_signal_count = 0
    english_signal_count = 0
    for name in SELECTED_FILES:
        path = phd_dir / name
        if not path.exists():
            sources.append({"name": name, "status": "missing"})
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        paper_signal_count += count_keywords(text, PAPER_KEYWORDS)
        english_signal_count += count_keywords(text, ENGLISH_KEYWORDS)
        sources.append(
            {
                "name": name,
                "status": "ok",
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone(timedelta(hours=8))).isoformat(),
                "size_bytes": path.stat().st_size,
            }
        )
    return sources, paper_signal_count, english_signal_count


def build_summary(phd_dir: Path, now: datetime | None = None) -> dict:
    current = now or beijing_now()
    sources, paper_signal_count, english_signal_count = read_selected_sources(phd_dir)
    source_status = "ok" if any(source["status"] == "ok" for source in sources) else "missing"
    return {
        "updated_at": current.isoformat(),
        "source_status": source_status,
        "mainlines": ["论文", "英语"],
        "paper": {
            "current_focus": "论文修改与理论机制梳理",
            "next_actions": ["推进一处可交付修改", "补强一条文献或机制链条"],
            "signal_count": paper_signal_count,
        },
        "english": {
            "current_focus": "博士申请相关英语能力准备",
            "next_actions": ["输入训练", "写作或口语输出", "表达积累"],
            "signal_count": english_signal_count,
        },
        "sources": sources,
        "privacy_note": "Only file names, mtimes, sizes, and keyword counts are uploaded; source text is not uploaded.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact public-safe PhD mainline summary.")
    parser.add_argument("--phd-dir", type=Path, default=DEFAULT_PHD_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_summary(args.phd_dir)
    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


DEFAULT_CLI = Path("D:/Lark/lark-cli-v1.0.51-windows-amd64/lark-cli.exe")
DEFAULT_USER_ID = "ou_bcd723dafdadfc604e0b66b4e8bb9f32"


def build_ascii_content(text: str) -> str:
    return json.dumps({"text": text}, ensure_ascii=True)


def send_text(cli: Path, user_id: str, text: str, idempotency_key: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(cli),
            "im",
            "+messages-send",
            "--as",
            "bot",
            "--user-id",
            user_id,
            "--msg-type",
            "text",
            "--content",
            build_ascii_content(text),
            "--idempotency-key",
            idempotency_key,
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send UTF-8 text through lark-cli using ASCII JSON escaping.")
    parser.add_argument("--cli", type=Path, default=DEFAULT_CLI)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--message-file", type=Path, required=True)
    parser.add_argument("--idempotency-key", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = args.message_file.read_text(encoding="utf-8")
    result = send_text(args.cli, args.user_id, text, args.idempotency_key)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request


def build_message() -> str:
    now = dt.datetime.utcnow() + dt.timedelta(hours=8)
    date_text = now.strftime("%Y-%m-%d")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    extra = os.environ.get("TODAY_EXTRA", "").strip()

    lines = [
        f"【09:00 PhD 申请主线计划｜{date_text} {weekday}】",
        "",
        "今日默认主线：清华公管博士申请准备。",
        "",
        "今日 focus：",
        "1. 推进一项可交付的 PhD 申请材料：研究计划、PS、CV、导师匹配或 writing sample。",
        "2. 留出 2-3 小时深度工作块，不让零散事务挤掉主线。",
        "3. 晚上做 5 分钟复盘：完成了什么、卡在哪里、明天第一件事是什么。",
        "",
        "建议时间块：",
        "09:00-09:20 明确今日 PhD 申请最小交付物",
        "09:20-11:50 PhD 深度工作：申请材料/研究计划/论文支撑材料",
        "11:50-12:10 记录进展与下一步",
        "14:00-15:30 文献、导师、项目或材料补充",
        "15:40-16:30 行政沟通/邮件/资料整理",
        "16:40-17:30 处理其他项目维护任务",
        "21:30-21:40 今日复盘，锁定明早第一步",
        "",
        "需要你确认：本周 PhD 申请最必须完成的 1-3 件事是什么？",
    ]

    if extra:
        lines.extend(["", f"今日补充：{extra}"])

    lines.extend(
        [
            "",
            "说明：这是云端 09:00 基础版提醒；本机 Codex 开机后可再补发基于本地项目进展的详细版。",
        ]
    )
    return "\n".join(lines)


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


def send_text(token: str, user_id: str, text: str) -> dict:
    return post_json(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
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
        token = get_tenant_access_token(app_id, app_secret)
        result = send_text(token, user_id, build_message())
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("code") == 0 else 1
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

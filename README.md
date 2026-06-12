# Morning Feishu Agent

每天北京时间 09:00 通过飞书开放平台 App 的 bot 身份发送基础版 PhD 申请日计划。

## 使用方式

1. 把本目录推到一个 GitHub 仓库。
2. 在 GitHub 仓库里进入 `Settings -> Secrets and variables -> Actions -> New repository secret`。
3. 添加 secrets：
   - `FEISHU_APP_ID`: 飞书开放平台 App ID
   - `FEISHU_APP_SECRET`: 飞书开放平台 App Secret
   - `FEISHU_USER_ID`: 接收消息的用户 open_id，例如 `ou_xxx`
4. 到 `Actions` 页面启用 workflow。

定时配置在 `.github/workflows/morning-feishu.yml`：

- `cron: "0 1 * * *"` 表示 UTC 01:00，也就是北京时间 09:00。
- GitHub Actions 定时任务可能有几分钟延迟，但不依赖你的电脑开机。

## 本地测试

PowerShell:

```powershell
$env:FEISHU_APP_ID="cli_xxx"
$env:FEISHU_APP_SECRET="xxx"
$env:FEISHU_USER_ID="ou_xxx"
python .\send_morning_plan.py
```

## 边界

这个云端版本负责 09:00 准时提醒和基础计划，不读取你本机 Codex 项目。
你 10 点开机后，本地 Codex 再补发“基于本机项目进展的详细版”。

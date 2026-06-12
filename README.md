# Morning Feishu Agent

每天北京时间 09:00 通过飞书机器人发送基础版 PhD 申请日计划。

## 使用方式

1. 在飞书里创建一个只给自己看的群，例如 `Agent 日报`。
2. 群设置里添加 `自定义机器人`，复制 Webhook URL。
3. 把本目录推到一个 GitHub 仓库。
4. 在 GitHub 仓库里进入 `Settings -> Secrets and variables -> Actions -> New repository secret`。
5. 添加 secret：
   - `FEISHU_WEBHOOK`: 飞书机器人 Webhook URL
   - `FEISHU_SECRET`: 可选；如果机器人启用了签名校验，就填签名密钥
6. 到 `Actions` 页面启用 workflow。

定时配置在 `.github/workflows/morning-feishu.yml`：

- `cron: "0 1 * * *"` 表示 UTC 01:00，也就是北京时间 09:00。
- GitHub Actions 定时任务可能有几分钟延迟，但不依赖你的电脑开机。

## 本地测试

PowerShell:

```powershell
$env:FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
python .\send_morning_plan.py
```

如果启用了签名：

```powershell
$env:FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
$env:FEISHU_SECRET="你的签名密钥"
python .\send_morning_plan.py
```

## 边界

这个云端版本负责 09:00 准时提醒和基础计划，不读取你本机 Codex 项目。
你 10 点开机后，本地 Codex 再补发“基于本机项目进展的详细版”。

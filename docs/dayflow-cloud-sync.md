# Dayflow Cloud Sync

This setup keeps Dayflow local-first, but sends compact task snapshots to a free Cloudflare Worker + KV endpoint whenever Dayflow saves state. GitHub Actions reads that endpoint at the morning send time and falls back to `data/dayflow/*.json` if the cloud endpoint is not configured or unavailable.

## Files

- Dayflow app client: `D:\try\cloud-sync.js`
- Dayflow save hook: `D:\try\app.js`
- Worker: `D:\Lark\morning-feishu-agent\cloudflare\dayflow-worker.mjs`
- Worker config template: `D:\Lark\morning-feishu-agent\cloudflare\wrangler.toml.example`
- GitHub reader: `D:\Lark\morning-feishu-agent\send_morning_plan.py`
- GitHub workflow: `D:\Lark\morning-feishu-agent\.github\workflows\morning-feishu.yml`

## Cloudflare Free Plan Fit

For one personal Dayflow instance, the free tier is enough. Workers Free allows 100,000 requests per day. Workers KV is available on the Free plan, with 100,000 reads per day, 1,000 writes per day, and 1 GB stored data. Dayflow usually writes only when tasks change, and GitHub reads once during the morning send window.

## Deploy Worker

Install and log in to Wrangler if needed:

```powershell
npm install -g wrangler
wrangler login
```

Create a KV namespace:

```powershell
wrangler kv namespace create DAYFLOW_KV
```

Copy the template and replace the namespace id:

```powershell
Copy-Item D:\Lark\morning-feishu-agent\cloudflare\wrangler.toml.example D:\Lark\morning-feishu-agent\cloudflare\wrangler.toml
notepad D:\Lark\morning-feishu-agent\cloudflare\wrangler.toml
```

Set two independent tokens. Use long random strings:

```powershell
cd D:\Lark\morning-feishu-agent\cloudflare
wrangler secret put DAYFLOW_WRITE_TOKEN
wrangler secret put DAYFLOW_READ_TOKEN
wrangler deploy
```

After deployment, keep the Worker URL. It should look like:

```text
https://dayflow-cloud-sync.mihoyo196006-dayflow.workers.dev/dayflow/current
```

## Configure Dayflow

Open Dayflow, then run this once in the app DevTools console:

```javascript
window.DayflowCloudSync.configure({
  enabled: true,
  endpoint: "https://dayflow-cloud-sync.mihoyo196006-dayflow.workers.dev/dayflow/current",
  writeToken: "<DAYFLOW_WRITE_TOKEN>",
  deviceId: "hh-windows-dayflow"
});
```

The next Dayflow save will POST a compact payload. It uploads both today's and yesterday's dated snapshots so the 09:00 GitHub job can request yesterday even if Dayflow was already edited this morning.

To disable sync:

```javascript
window.DayflowCloudSync.configure({ enabled: false });
```

## Configure GitHub Actions

In the GitHub repository secrets for `mihoyo196006-rgb/Agent_try01`, add:

```text
DAYFLOW_CLOUD_ENDPOINT=https://dayflow-cloud-sync.mihoyo196006-dayflow.workers.dev/dayflow/current
DAYFLOW_READ_TOKEN=<DAYFLOW_READ_TOKEN>
```

Do not put `DAYFLOW_WRITE_TOKEN` in GitHub. GitHub only needs read access.

## Verify

Run local tests:

```powershell
cd D:\try
node --test tests/dayflow-cloud-sync.test.mjs

cd D:\Lark\morning-feishu-agent
python -m unittest discover -s tests -v
node --test tests/dayflow_cloud_worker.test.mjs
```

After configuring Dayflow and making one task change, test the Worker read endpoint:

```powershell
$headers = @{ Authorization = "Bearer <DAYFLOW_READ_TOKEN>" }
Invoke-RestMethod -Headers $headers "https://dayflow-cloud-sync.mihoyo196006-dayflow.workers.dev/dayflow/current"
```

The response should contain `source_status: ok`, `snapshot_date`, `counts`, `done_tasks`, `open_tasks`, and `snapshots`.

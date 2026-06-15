# Dayflow Feishu Daily Flow Design

Date: 2026-06-16
Status: draft for user review

## Goal

Build a low-token daily workflow that turns local Dayflow task completion into two Feishu bot messages every morning:

1. 昨日总结
2. 今日规划

The workflow must still send at 09:30 Beijing time when the local computer is powered off. If the computer was off and no fresh Dayflow snapshot was uploaded, the morning message must clearly say that the plan is based on the latest available snapshot.

The default path should use rule-based generation and spend 0 model tokens. Any optional model-assisted path must use only compact JSON summaries, never full Codex history or broad project scans.

## Confirmed Constraints

- Dayflow task data is local-first and is currently readable from the Windows app data LevelDB cache.
- GitHub Actions can send Feishu bot messages while the local computer is off.
- GitHub Actions cannot directly read local Dayflow or `D:\PHD_application`.
- The PhD main line for this automation is not generic application management. Morning plans should focus on:
  - 论文
  - 英语
- The daily Feishu output should be concise and split into two separate messages.

## Architecture

The system has two sides:

1. Local snapshot side
   - Runs on the Windows machine when it is on.
   - Reads Dayflow from local cache.
   - Compresses the result into small JSON files.
   - Pushes those files to the GitHub repository.

2. Cloud delivery side
   - Runs in GitHub Actions at 09:30 Beijing time.
   - Reads the latest committed Dayflow and PhD mainline summaries.
   - Builds two Feishu messages.
   - Sends both messages through the existing Feishu bot credentials.

This keeps the delivery reliable while accepting that local-only Dayflow data can only be refreshed when the machine was recently on.

## Local Snapshot Flow

Use Windows Task Scheduler to run the local snapshot script twice per day:

- 23:50: main snapshot for the day that is about to end.
- 00:10: supplement snapshot to catch late completions near midnight.

The 23:50 snapshot is the primary source for "yesterday". The 00:10 snapshot may update completion status but must not replace the whole day with a new empty "today" view after Dayflow refreshes.

The snapshot script writes:

- `data/dayflow/YYYY-MM-DD-2350.json`
- `data/dayflow/YYYY-MM-DD-0010.json`
- `data/dayflow/latest.json`

Each snapshot should contain only compact fields:

```json
{
  "snapshot_date": "2026-06-16",
  "captured_at": "2026-06-16T23:50:00+08:00",
  "capture_kind": "main",
  "source_status": "ok",
  "freshness": {
    "is_expected_window": true,
    "age_hours_at_commit": 0
  },
  "counts": {
    "total": 8,
    "done": 5,
    "open": 3
  },
  "done_tasks": [
    {"title": "修改论文引言", "domain": "paper", "priority": "high"}
  ],
  "open_tasks": [
    {"title": "整理英语表达", "domain": "english", "priority": "medium"}
  ]
}
```

Task notes should be omitted by default unless they are short and necessary. This prevents accidental large payloads and keeps model input small if an optional model pass is enabled later.

After writing snapshots, the local job commits and pushes only `data/dayflow/*.json` plus any compact PhD summary files produced by the same local pipeline.

## PhD Mainline Summary

The workflow should keep a compact PhD summary file in the repository:

- `data/phd/mainline.json`

It should be generated locally from selected files in `D:\PHD_application`, not by scanning all Codex history. The summary should be small and stable:

```json
{
  "updated_at": "2026-06-16T23:50:00+08:00",
  "mainlines": ["论文", "英语"],
  "paper": {
    "current_focus": "论文修改与理论机制梳理",
    "next_actions": ["推进一处可交付修改", "补强一条文献或机制链条"]
  },
  "english": {
    "current_focus": "博士申请相关英语能力准备",
    "next_actions": ["输入训练", "写作或口语输出", "表达积累"]
  }
}
```

The summary may be manually maintained at first. Automatic extraction can be added later, but it must stay selective and compact.

## Cloud Morning Flow

GitHub Actions runs every day at Beijing 09:30:

- Cron: `30 1 * * *` UTC.
- Manual trigger remains available through `workflow_dispatch`.

The job reads:

- the newest Dayflow main snapshot for yesterday;
- the 00:10 supplement snapshot when available;
- `data/dayflow/latest.json` as fallback;
- `data/phd/mainline.json`;
- Feishu app secret from GitHub Actions secrets.

It then sends two Feishu text messages.

## Freshness Rules

At 09:30, the cloud job checks whether yesterday has a valid 23:50 or 00:10 snapshot.

Fresh:

- A 23:50 main snapshot exists for yesterday, or
- a 00:10 supplement exists that refers to yesterday's tasks.

Stale:

- no expected snapshot exists;
- latest snapshot is older than the previous evening;
- snapshot source status is not `ok`.

When stale, both messages must include a short notice:

`未收到昨晚 Dayflow 新快照，以下基于最近一次快照和 PhD 主线生成。`

The send should still continue.

## Message 1: 昨日总结

Only two sections are allowed:

1. 完成情况
   - completed task count and total task count;
   - completed task titles;
   - unfinished task count when useful.

2. 对主线的帮助
   - explain how completed tasks supported the PhD main line;
   - focus on 论文 and 英语;
   - do not add any third section.

Example shape:

```text
昨日总结｜2026-06-16

完成情况：
今天 Dayflow 记录 8 项任务，完成 5 项。
已完成：修改论文引言；整理英语表达；完成一组英文复述。

对主线的帮助：
论文方面，今天的引言修改推进了可交付文本；英语方面，表达整理和复述训练支持博士申请英语能力的持续积累。
```

## Message 2: 今日规划

The plan is cut into one-hour blocks and focuses on two main lines:

- 论文
- 英语

Default planning rules:

- Put the highest-value paper task in the first deep work block.
- Include at least one concrete English input or output block.
- Do not include default blocks outside 论文 and 英语.
- Only insert a non-paper/non-English item when Dayflow or PhD summary explicitly marks it as a hard deadline.

Example shape:

```text
今日规划｜2026-06-17

09:30-10:30 论文：确认今天要推进的一处修改，写出最小可交付段落。
10:30-11:30 论文：补强理论机制或文献支撑。
11:30-12:30 英语：博士英语/雅思输入，记录可复用表达。
14:00-15:00 论文：继续修改结果解释或方法表述。
15:00-16:00 英语：写作或口语输出，并整理错题/表达。
16:00-17:00 论文：收束今日修改，记录明天第一步。
```

## Token Budget

Default generation uses deterministic templates and costs 0 model tokens.

Optional model-assisted generation can be added behind an explicit switch:

- Environment variable: `USE_LLM_SUMMARY=true`.
- Input limited to:
  - one Dayflow compact snapshot;
  - one PhD compact summary;
  - one short prompt.
- No full repository scan.
- No Codex session history scan.
- If the model call fails or the estimated input is too large, fall back to the rule-based generator.

The weekly default should therefore remain 0 tokens. Even with the optional model path enabled, the payload should stay small enough to be far below 1 percent of weekly usage.

## Error Handling

- Dayflow read fails locally:
  - write a snapshot with `source_status: "error"`;
  - include the error string in a short field;
  - still commit and push so the cloud job can explain the missing data.

- Git push fails locally:
  - leave the snapshot files on disk;
  - log the error;
  - retry on the next scheduled local run.

- GitHub Actions cannot find a fresh snapshot:
  - send stale-data notice;
  - use latest snapshot and PhD summary.

- Feishu send fails:
  - fail the workflow with clear stderr output;
  - keep `workflow_dispatch` for manual retry.

## Testing

Local tests:

- Run the Dayflow reader and verify compact JSON is written.
- Simulate 23:50 and 00:10 snapshots.
- Verify stale snapshot detection with intentionally old files.
- Verify the generator produces exactly two messages.

Cloud tests:

- Run GitHub Actions manually with sample JSON files.
- Confirm two Feishu messages arrive.
- Confirm stale-data notice appears when expected snapshots are missing.

Regression checks:

- Ensure no generated message includes default categories outside 论文 and 英语.
- Ensure "昨日总结" has only:
  - 完成情况;
  - 对主线的帮助.

## Implementation Scope

This design covers:

- compact local Dayflow snapshot files;
- compact PhD mainline summary file;
- local scheduled snapshot and push flow;
- GitHub Actions 09:30 cloud sender;
- two Feishu messages;
- stale-data fallback;
- default zero-token generation.

This design does not cover:

- building a Dayflow cloud API;
- replacing Dayflow with another task manager;
- broad automatic analysis of all PhD files;
- recurring full Codex-context summarization.

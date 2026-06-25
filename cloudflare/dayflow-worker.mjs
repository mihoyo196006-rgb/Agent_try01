const CURRENT_KEY = "dayflow:current";
const BEIJING_OFFSET_MS = 8 * 60 * 60 * 1000;

const DOMAIN_LABELS = {
  paper: "论文",
  english: "英语",
  other: "其他",
};

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function missingSnapshot() {
  return {
    snapshot_date: "",
    source_status: "missing",
    counts: { total: 0, done: 0, open: 0 },
    done_tasks: [],
    open_tasks: [],
  };
}

function dateKey(date) {
  return date.toISOString().slice(0, 10);
}

function beijingDate(now = new Date()) {
  return new Date(now.getTime() + BEIJING_OFFSET_MS);
}

function addDays(date, amount) {
  const next = new Date(date);
  next.setUTCDate(next.getUTCDate() + amount);
  return next;
}

function scheduledTargetDate(now = new Date()) {
  return dateKey(addDays(beijingDate(now), -1));
}

function deliveryDate(now = new Date()) {
  return dateKey(beijingDate(now));
}

function deliveryKey(dateText) {
  return `feishu:delivery:${dateText}`;
}

function tasksByDomain(tasks, domain) {
  return (tasks || []).filter((task) => task?.domain === domain);
}

function taskTitle(task) {
  return String(task?.title || "未命名任务").trim();
}

function formatTitles(tasks, emptyText, limit = 4) {
  if (!tasks.length) return [`  - ${emptyText}`];
  const lines = tasks.slice(0, limit).map((task) => `  - ${taskTitle(task)}`);
  const remaining = tasks.length - limit;
  if (remaining > 0) lines.push(`  - 另有 ${remaining} 项未展开`);
  return lines;
}

function paperProgressLine(donePaper, openPaper) {
  if (donePaper.length && openPaper.length) {
    return `论文有实质推进：完成 ${donePaper.length} 项，但仍有 ${openPaper.length} 项需要今天接上。`;
  }
  if (donePaper.length) {
    return `论文有实质推进：完成 ${donePaper.length} 项，今天应把成果固化为文字或模型修改。`;
  }
  if (openPaper.length) {
    return `论文昨天没有形成完成记录，仍有 ${openPaper.length} 项悬而未决，今天优先补上。`;
  }
  return "昨天没有明确的论文任务记录，今天需要主动把主线拉回论文。";
}

function buildMorningMessage(snapshot) {
  const counts = snapshot.counts || {};
  const doneTasks = snapshot.done_tasks || [];
  const openTasks = snapshot.open_tasks || [];
  const donePaper = tasksByDomain(doneTasks, "paper");
  const openPaper = tasksByDomain(openTasks, "paper");
  const doneEnglish = tasksByDomain(doneTasks, "english");
  const openEnglish = tasksByDomain(openTasks, "english");

  return [
    `昨日论文进展｜${snapshot.snapshot_date || ""}`,
    "",
    "论文判断",
    `  ${paperProgressLine(donePaper, openPaper)}`,
    "",
    "已推进",
    ...formatTitles(donePaper, "暂无论文完成记录"),
    "",
    "未完成/今日接力",
    ...formatTitles(openPaper, "暂无论文遗留项"),
    "",
    "其他信号",
    `  ${DOMAIN_LABELS.english}：完成 ${doneEnglish.length} 项，未完成 ${openEnglish.length} 项`,
    `  DayFlow：共 ${counts.total || 0} 项，完成 ${counts.done || 0} 项，未完成 ${counts.open || 0} 项`,
  ].join("\n");
}

async function loadSnapshotForDate(env, targetDate) {
  const stored = await env.DAYFLOW_KV.get(CURRENT_KEY);
  if (!stored) return missingSnapshot();
  const payload = JSON.parse(stored);
  const snapshot = payload.snapshots?.[targetDate] || (payload.snapshot_date === targetDate ? payload : null);
  if (!snapshot) return missingSnapshot();
  return {
    ...snapshot,
    synced_at_cloud: payload.synced_at_cloud,
    synced_source: payload.synced_source || "dayflow-worker",
  };
}

async function postJson(url, payload, token) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  return body;
}

async function getTenantAccessToken(env) {
  const result = await postJson("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", {
    app_id: env.FEISHU_APP_ID,
    app_secret: env.FEISHU_APP_SECRET,
  });
  if (result.code !== 0 || !result.tenant_access_token) {
    throw new Error(`Feishu token error: ${JSON.stringify(result)}`);
  }
  return result.tenant_access_token;
}

async function sendFeishuText(env, text, messageUuid) {
  const token = await getTenantAccessToken(env);
  const url = `https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id&uuid=${encodeURIComponent(messageUuid)}`;
  const result = await postJson(
    url,
    {
      receive_id: env.FEISHU_USER_ID,
      msg_type: "text",
      content: JSON.stringify({ text }),
    },
    token,
  );
  if (result.code !== 0) {
    throw new Error(`Feishu send error: ${JSON.stringify(result)}`);
  }
  return result;
}

async function sendScheduledMorningMessage(env, now = new Date()) {
  const today = deliveryDate(now);
  const key = deliveryKey(today);
  const existing = await env.DAYFLOW_KV.get(key);
  if (existing) {
    return { ok: true, skipped: true, reason: "already_sent", key };
  }

  const targetDate = scheduledTargetDate(now);
  const snapshot = await loadSnapshotForDate(env, targetDate);
  const message = buildMorningMessage(snapshot);
  const messageUuid = `dayflow-morning-${today}`;
  const result = await sendFeishuText(env, message, messageUuid);
  const marker = {
    date: today,
    sent_at: now.toISOString(),
    snapshot_date: snapshot.snapshot_date || "",
    counts: snapshot.counts || { total: 0, done: 0, open: 0 },
    message_id: String(result.data?.message_id || ""),
    chat_id: String(result.data?.chat_id || ""),
  };
  await env.DAYFLOW_KV.put(key, JSON.stringify(marker));
  return { ok: true, marker };
}

function bearerToken(request) {
  const header = request.headers.get("authorization") || "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  return match ? match[1] : "";
}

function isAuthorized(request, expectedToken) {
  return Boolean(expectedToken) && bearerToken(request) === expectedToken;
}

async function handleGet(request, env) {
  if (!isAuthorized(request, env.DAYFLOW_READ_TOKEN)) {
    return jsonResponse({ error: "unauthorized" }, 401);
  }
  const stored = await env.DAYFLOW_KV.get(CURRENT_KEY);
  if (!stored) {
    return jsonResponse(missingSnapshot());
  }
  const payload = JSON.parse(stored);
  const requestedDate = new URL(request.url).searchParams.get("date");
  if (requestedDate) {
    const snapshot = payload.snapshots?.[requestedDate];
    if (!snapshot) {
      return jsonResponse(missingSnapshot());
    }
    return jsonResponse({
      ...snapshot,
      synced_at_cloud: payload.synced_at_cloud,
      synced_source: payload.synced_source || "dayflow-worker",
    });
  }
  return jsonResponse(payload);
}

async function handlePost(request, env) {
  if (!isAuthorized(request, env.DAYFLOW_WRITE_TOKEN)) {
    return jsonResponse({ error: "unauthorized" }, 401);
  }

  let payload;
  try {
    payload = await request.json();
  } catch {
    return jsonResponse({ error: "invalid_json" }, 400);
  }

  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return jsonResponse({ error: "invalid_payload" }, 400);
  }

  const snapshot = {
    ...payload,
    synced_at_cloud: new Date().toISOString(),
    synced_source: "dayflow-worker",
  };
  await env.DAYFLOW_KV.put(CURRENT_KEY, JSON.stringify(snapshot));
  return jsonResponse({ ok: true });
}

export default {
  async scheduled(controller, env) {
    await sendScheduledMorningMessage(env);
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/dayflow/current") {
      return jsonResponse({ error: "not_found" }, 404);
    }
    if (request.method === "GET") {
      return handleGet(request, env);
    }
    if (request.method === "POST") {
      return handlePost(request, env);
    }
    return jsonResponse({ error: "method_not_allowed" }, 405);
  },
};

export {
  buildMorningMessage,
  deliveryDate,
  deliveryKey,
  scheduledTargetDate,
  sendScheduledMorningMessage,
};

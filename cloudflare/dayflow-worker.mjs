const CURRENT_KEY = "dayflow:current";

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

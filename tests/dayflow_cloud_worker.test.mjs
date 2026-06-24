import assert from "node:assert/strict";
import test from "node:test";

import worker from "../cloudflare/dayflow-worker.mjs";

class MemoryKv {
  constructor() {
    this.values = new Map();
  }

  async get(key) {
    return this.values.get(key) || null;
  }

  async put(key, value) {
    this.values.set(key, value);
  }
}

function env() {
  return {
    DAYFLOW_KV: new MemoryKv(),
    DAYFLOW_WRITE_TOKEN: "write-token",
    DAYFLOW_READ_TOKEN: "read-token",
  };
}

test("POST /dayflow/current stores the current compact snapshot", async () => {
  const testEnv = env();
  const response = await worker.fetch(
    new Request("https://worker.example/dayflow/current", {
      method: "POST",
      headers: {
        authorization: "Bearer write-token",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        snapshot_date: "2026-06-23",
        source_status: "ok",
        counts: { total: 1, done: 1, open: 0 },
        done_tasks: [{ title: "论文任务", domain: "paper", priority: "high" }],
        open_tasks: [],
      }),
    }),
    testEnv,
  );

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { ok: true });

  const stored = JSON.parse(await testEnv.DAYFLOW_KV.get("dayflow:current"));
  assert.equal(stored.snapshot_date, "2026-06-23");
  assert.equal(stored.source_status, "ok");
  assert.equal(stored.synced_source, "dayflow-worker");
  assert.match(stored.synced_at_cloud, /^\d{4}-\d{2}-\d{2}T/);
});

test("GET /dayflow/current returns the stored snapshot", async () => {
  const testEnv = env();
  await testEnv.DAYFLOW_KV.put(
    "dayflow:current",
    JSON.stringify({
      snapshot_date: "2026-06-23",
      source_status: "ok",
      counts: { total: 1, done: 1, open: 0 },
      done_tasks: [],
      open_tasks: [],
    }),
  );

  const response = await worker.fetch(
    new Request("https://worker.example/dayflow/current", {
      headers: { authorization: "Bearer read-token" },
    }),
    testEnv,
  );

  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.snapshot_date, "2026-06-23");
  assert.equal(payload.source_status, "ok");
});

test("GET /dayflow/current?date returns a dated snapshot from the stored bundle", async () => {
  const testEnv = env();
  await testEnv.DAYFLOW_KV.put(
    "dayflow:current",
    JSON.stringify({
      snapshot_date: "2026-06-24",
      source_status: "ok",
      counts: { total: 2, done: 0, open: 2 },
      done_tasks: [],
      open_tasks: [],
      snapshots: {
        "2026-06-23": {
          snapshot_date: "2026-06-23",
          source_status: "ok",
          counts: { total: 1, done: 1, open: 0 },
          done_tasks: [{ title: "论文任务", domain: "paper", priority: "high" }],
          open_tasks: [],
        },
      },
    }),
  );

  const response = await worker.fetch(
    new Request("https://worker.example/dayflow/current?date=2026-06-23", {
      headers: { authorization: "Bearer read-token" },
    }),
    testEnv,
  );

  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.snapshot_date, "2026-06-23");
  assert.deepEqual(payload.counts, { total: 1, done: 1, open: 0 });
  assert.equal(payload.synced_source, "dayflow-worker");
});

test("GET /dayflow/current returns a missing snapshot before first sync", async () => {
  const response = await worker.fetch(
    new Request("https://worker.example/dayflow/current", {
      headers: { authorization: "Bearer read-token" },
    }),
    env(),
  );

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    snapshot_date: "",
    source_status: "missing",
    counts: { total: 0, done: 0, open: 0 },
    done_tasks: [],
    open_tasks: [],
  });
});

test("POST and GET reject the wrong token", async () => {
  const writeResponse = await worker.fetch(
    new Request("https://worker.example/dayflow/current", {
      method: "POST",
      headers: { authorization: "Bearer wrong", "content-type": "application/json" },
      body: JSON.stringify({ snapshot_date: "2026-06-23" }),
    }),
    env(),
  );
  assert.equal(writeResponse.status, 401);

  const readResponse = await worker.fetch(
    new Request("https://worker.example/dayflow/current", {
      headers: { authorization: "Bearer wrong" },
    }),
    env(),
  );
  assert.equal(readResponse.status, 401);
});

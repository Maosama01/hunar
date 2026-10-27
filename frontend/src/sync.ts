// Offline sync engine. Every write is first stored in the Dexie outbox; this module replays the
// outbox IN ORDER (by seq) through POST /api/sync in small batches whenever the server is reachable:
// on the 'online' event, on app start, every 20 s, after each new write, and on "Sync now".
//
// Server results per op: "applied" or "duplicate" -> the op is removed; "rejected" -> the op stays,
// marked rejected, and the queue stops so later ops (which may depend on it) are not applied out of
// order. The user sees the error and can retry or discard that op.
import { api, ApiError, apiUrl, detailText, errorText, NetworkError, type EvidenceOut, type OpKind } from "./api";
import { refreshAssessment, refreshAssessmentList } from "./data";
import { db, type OutboxOp } from "./db";
import { thumbFromUrl } from "./photo";
import { getStatus, setStatus } from "./status";
import { nowIso, uuid } from "./util";

const BATCH_MAX_OPS = 10;
const BATCH_MAX_BYTES = 2_500_000; // photos are ~0.2-0.5 MB each as base64
const INTERVAL_MS = 20_000;
/** A single op that makes the server fail (HTTP 5xx with the server up) this often is marked rejected. */
const MAX_SERVER_ERRORS = 3;

// ---- Writing to the outbox ------------------------------------------------------------------------

export interface EnqueueOpts {
  assessment_id?: string | null;
  meta?: Record<string, unknown>;
  op_id?: string;
}

/** Add an op inside an existing Dexie transaction that includes db.outbox. */
export async function addOp(kind: OpKind, payload: Record<string, unknown>, opts: EnqueueOpts = {}): Promise<string> {
  const op_id = opts.op_id ?? uuid();
  const op: OutboxOp = {
    op_id,
    kind,
    payload,
    created_at: nowIso(),
    status: "pending",
    error: null,
    attempts: 0,
    assessment_id: opts.assessment_id ?? (typeof payload.assessment_id === "string" ? payload.assessment_id : null),
    meta: opts.meta,
  };
  await db.outbox.add(op);
  return op_id;
}

export async function enqueue(kind: OpKind, payload: Record<string, unknown>, opts: EnqueueOpts = {}): Promise<string> {
  const id = await db.transaction("rw", db.outbox, () => addOp(kind, payload, opts));
  requestSync();
  return id;
}

/** Queue one checklist tick. Consecutive ticks on the same task are merged into the last queued op
 * if (and only if) it is the newest op in the outbox and has never been sent, so order is kept. */
export async function enqueueTick(
  assessmentId: string,
  taskId: string,
  itemId: string,
  value: boolean,
  actor: string,
): Promise<void> {
  await db.transaction("rw", db.outbox, async () => {
    const last = await db.outbox.orderBy("seq").last();
    if (
      last &&
      last.kind === "checklist.set" &&
      last.status === "pending" &&
      last.attempts === 0 &&
      last.payload.assessment_id === assessmentId &&
      last.payload.task_id === taskId &&
      last.payload.actor === actor
    ) {
      const ticks = { ...(last.payload.ticks as Record<string, boolean>), [itemId]: value };
      await db.outbox.update(last.seq!, { payload: { ...last.payload, ticks } });
      return;
    }
    await addOp("checklist.set", { assessment_id: assessmentId, task_id: taskId, ticks: { [itemId]: value }, actor });
  });
  requestSync();
}

// ---- User actions on a refused op -------------------------------------------------------------------

export async function retryOp(seq: number): Promise<void> {
  await db.outbox.update(seq, { status: "pending", error: null });
  await syncNow();
}

/** Drop a refused op and the local records that only exist because of it. */
export async function discardOp(seq: number): Promise<void> {
  await db.transaction("rw", [db.outbox, db.photos, db.workers, db.assessments], async () => {
    const op = await db.outbox.get(seq);
    if (!op) return;
    await db.outbox.delete(seq);
    if (op.kind === "evidence.add") await db.photos.delete(op.op_id);
    if (op.kind === "worker.create") await db.workers.delete(String(op.payload.id));
    if (op.kind === "assessment.create") await db.assessments.delete(String(op.payload.id));
  });
  await syncNow();
}

// ---- Replay ------------------------------------------------------------------------------------------

let running: Promise<void> | null = null;
let again = false;
let debounce: number | undefined;

/** Ask for a sync soon (coalesces bursts of writes such as several checklist taps). */
export function requestSync(delayMs = 300): void {
  window.clearTimeout(debounce);
  debounce = window.setTimeout(() => void syncNow(), delayMs);
}

export function syncNow(): Promise<void> {
  if (running) {
    again = true;
    return running;
  }
  running = (async () => {
    try {
      do {
        again = false;
        await withTabLock(runOnce);
      } while (again);
    } finally {
      running = null;
    }
  })();
  return running;
}

/** Only one browser tab replays the outbox at a time. */
async function withTabLock(fn: () => Promise<void>): Promise<void> {
  const locks = (navigator as Navigator & { locks?: LockManager }).locks;
  if (locks && typeof locks.request === "function") {
    await locks.request("hunar-sync", { ifAvailable: true }, async (lock) => {
      if (lock) await fn();
    });
  } else {
    await fn();
  }
}

function estimateSize(op: OutboxOp): number {
  const b64 = op.payload.image_b64;
  return (typeof b64 === "string" ? b64.length : 0) + 1000;
}

/** Take the next batch and mark it "sending" in one transaction, so a checklist merge cannot slip
 * in between reading and sending. */
async function takeBatch(limit: number): Promise<OutboxOp[]> {
  return db.transaction("rw", db.outbox, async () => {
    const head = await db.outbox.orderBy("seq").limit(BATCH_MAX_OPS).toArray();
    const batch: OutboxOp[] = [];
    let bytes = 0;
    for (const op of head) {
      if (op.status !== "pending" || batch.length >= limit) break; // a refused op blocks the rest
      const size = estimateSize(op);
      if (batch.length > 0 && bytes + size > BATCH_MAX_BYTES) break;
      batch.push(op);
      bytes += size;
    }
    for (const op of batch) {
      op.status = "sending";
      op.attempts += 1;
      await db.outbox.put(op);
    }
    return batch;
  });
}

async function backToPending(batch: OutboxOp[], error: string | null = null): Promise<void> {
  await db.transaction("rw", db.outbox, async () => {
    for (const op of batch) {
      const cur = await db.outbox.get(op.seq!);
      if (cur && cur.status === "sending") await db.outbox.update(op.seq!, { status: "pending", error });
    }
  });
}

async function onApplied(op: OutboxOp, result: unknown, touched: Set<string>, thumbs: [string, string][]) {
  if (op.kind === "evidence.add") {
    const ev = result as EvidenceOut;
    // The full-size raw image goes with the op; drop the raw local preview too.
    await db.photos.update(op.op_id, { status: "synced", server: ev, thumb: null, thumb_kind: null });
    if (ev?.image_url) thumbs.push([op.op_id, ev.image_url]);
  }
  if (op.assessment_id) touched.add(op.assessment_id);
}

async function runOnce(): Promise<void> {
  setStatus({ online: navigator.onLine });
  if (!navigator.onLine) return;
  const pendingOps = await db.outbox.count();
  const pendingRatings = await db.ratings.count();
  if (pendingOps === 0 && pendingRatings === 0) return;

  setStatus({ syncing: true });
  const touched = new Set<string>();
  const thumbs: [string, string][] = [];
  let failed: string | null = null;
  try {
    // Ops left "sending" by an interrupted run are safe to resend: the server dedupes by op_id.
    await db.outbox.where("status").equals("sending").modify({ status: "pending" });
    let limit = BATCH_MAX_OPS;
    for (let guard = 0; guard < 1000; guard++) {
      const batch = await takeBatch(limit);
      if (batch.length === 0) break;
      let results;
      try {
        results = (await api.sync(batch.map((o) => ({ op_id: o.op_id, kind: o.kind, payload: o.payload })))).results;
      } catch (e) {
        if (e instanceof NetworkError) {
          await backToPending(batch);
          failed = e.message;
          break;
        }
        if (e instanceof ApiError) {
          if (batch.length > 1) {
            // Find the op the server cannot handle by sending one at a time.
            await backToPending(batch);
            limit = 1;
            continue;
          }
          const op = batch[0];
          const fatal = e.status < 500 || op.attempts >= MAX_SERVER_ERRORS;
          await db.outbox.update(op.seq!, { status: fatal ? "rejected" : "pending", error: errorText(e) });
          failed = errorText(e);
          break;
        }
        await backToPending(batch);
        throw e;
      }
      const byId = new Map(results.map((r) => [r.op_id, r]));
      let stop = false;
      for (const op of batch) {
        const r = byId.get(op.op_id);
        if (stop || !r) {
          // The server stops at the first refusal; ops after it were not processed.
          await db.outbox.update(op.seq!, { status: "pending" });
          continue;
        }
        if (r.status === "applied" || r.status === "duplicate") {
          await onApplied(op, r.result, touched, thumbs);
          await db.outbox.delete(op.seq!);
        } else {
          const msg = detailText(r.error) || "refused by the server";
          await db.outbox.update(op.seq!, { status: "rejected", error: msg });
          failed = msg;
          stop = true;
        }
      }
      if (stop) break;
      limit = BATCH_MAX_OPS;
    }
    if (!failed) {
      const head = await db.outbox.orderBy("seq").first();
      if (head?.status === "rejected") failed = head.error ?? "a queued change was refused";
    }
    const ratingsError = await flushRatings();
    failed = failed ?? ratingsError;
  } catch (e) {
    failed = errorText(e);
  } finally {
    setStatus({ syncing: false, lastError: failed, ...(failed ? {} : { lastSyncAt: nowIso() }) });
  }

  // Bring local copies up to date with what the server now holds.
  for (const [photoId, url] of thumbs) {
    const thumb = await thumbFromUrl(apiUrl(url));
    if (thumb) await db.photos.update(photoId, { thumb, thumb_kind: "server_blurred" });
  }
  if (touched.size && getStatus().reachable !== false) {
    await Promise.all(
      [...touched].map((id) =>
        refreshAssessment(id, { prescores: true, profile: true }).catch(() => undefined),
      ),
    );
    await refreshAssessmentList().catch(() => undefined);
  }
}

// ---- Rater ratings (POST /api/study/ratings is not part of /api/sync) --------------------------

/** Upload ratings stored while offline. Returns an error message when something failed. */
export async function flushRatings(): Promise<string | null> {
  const rows = await db.ratings.orderBy("id").toArray();
  for (const r of rows) {
    if (r.error) continue; // refused before; waits for the rater to discard it
    try {
      await api.addRating(r.payload);
      await db.ratings.delete(r.id!);
    } catch (e) {
      if (e instanceof NetworkError) return e.message;
      await db.ratings.update(r.id!, { error: errorText(e) });
    }
  }
  return null;
}

// ---- Loop --------------------------------------------------------------------------------------------

async function tick(): Promise<void> {
  const queued = (await db.outbox.count()) + (await db.ratings.count());
  if (queued > 0) {
    await syncNow();
  } else if (navigator.onLine) {
    try {
      await api.health(); // keeps the online/offline badge honest
    } catch {
      /* status already updated by the client */
    }
  }
}

/** Start background sync. Returns a function that stops it. */
export function startSyncLoop(): () => void {
  const onOnline = () => {
    setStatus({ online: true });
    void tick();
  };
  const onOffline = () => setStatus({ online: false });
  const onVisible = () => {
    if (document.visibilityState === "visible") void tick();
  };
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
  document.addEventListener("visibilitychange", onVisible);
  const timer = window.setInterval(() => void tick(), INTERVAL_MS);
  void tick();
  return () => {
    window.removeEventListener("online", onOnline);
    window.removeEventListener("offline", onOffline);
    document.removeEventListener("visibilitychange", onVisible);
    window.clearInterval(timer);
  };
}

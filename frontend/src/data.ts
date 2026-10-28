// Read side: refresh local copies from the API when online, and build screen views from
// "last server snapshot + queued local changes" so every screen renders the same offline and online.
import { liveQuery } from "dexie";
import { useEffect, useState } from "react";
import {
  api,
  apiUrl,
  ApiError,
  type AssessmentRow,
  type Decision,
  type EvidenceOut,
  type MappingResult,
  type PackSummary,
  type Rubrics,
  type Signoff,
} from "./api";
import { cacheGet, cachePut, CACHE, db, type OutboxOp, type Snapshot } from "./db";
import { isConnected } from "./status";
import { nowIso } from "./util";

// ---- Live queries --------------------------------------------------------------------------------

/** Subscribe to a Dexie live query. Returns undefined until the first result arrives. */
export function useLive<T>(querier: () => Promise<T> | T, deps: unknown[]): T | undefined {
  const [value, setValue] = useState<T | undefined>(undefined);
  useEffect(() => {
    const sub = liveQuery(querier).subscribe({
      next: (v) => setValue(() => v),
      error: (e: unknown) => console.warn("live query failed", e),
    });
    return () => sub.unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return value;
}

// ---- Reference data (packs, rubrics): cached for offline use ---------------------------------------

const lastRefresh: Record<string, number> = {};
const REF_TTL_MS = 5 * 60 * 1000;

async function refreshOnce(key: string, fn: () => Promise<void>, force = false): Promise<void> {
  if (!force && Date.now() - (lastRefresh[key] ?? 0) < REF_TTL_MS) return;
  if (!isConnected()) return; // offline: keep using the cached copy
  lastRefresh[key] = Date.now();
  try {
    await fn();
  } catch {
    lastRefresh[key] = 0; // try again next time
  }
}

export function refreshReference(force = false): Promise<void> {
  return Promise.all([
    refreshOnce("rubrics", async () => cachePut(CACHE.rubrics, await api.rubrics()), force),
    refreshOnce("packs", async () => cachePut(CACHE.packs, await api.packs()), force),
  ]).then(() => undefined);
}

export function useRubrics(): Rubrics | null | undefined {
  useEffect(() => {
    void refreshReference();
  }, []);
  return useLive(async () => (await cacheGet(CACHE.rubrics))?.value ?? null, []);
}

export function usePacks(): PackSummary[] | null | undefined {
  useEffect(() => {
    void refreshReference();
  }, []);
  return useLive(async () => (await cacheGet(CACHE.packs))?.value ?? null, []);
}

// ---- Assessments ---------------------------------------------------------------------------------

export async function refreshAssessmentList(): Promise<void> {
  await cachePut(CACHE.assessments, await api.assessments());
}

/** Fetch the server copy of an assessment (and optionally its pre scores / profile). A slower,
 * older request never overwrites a newer one. 404 is normal for an assessment not yet synced. */
export async function refreshAssessment(
  id: string,
  opts: { prescores?: boolean; profile?: boolean } = {},
): Promise<void> {
  const startedAt = nowIso();
  const [detail, prescores, profile] = await Promise.all([
    api.assessment(id),
    opts.prescores ? api.prescores(id) : Promise.resolve(undefined),
    opts.profile ? api.profile(id) : Promise.resolve(undefined),
  ]);
  await db.transaction("rw", db.snapshots, async () => {
    const prev = await db.snapshots.get(id);
    const next: Snapshot = { ...(prev ?? { id, detail, fetched_at: startedAt }), id };
    if (!prev || prev.fetched_at <= startedAt) {
      next.detail = detail;
      next.fetched_at = startedAt;
    }
    if (prescores && (!prev?.prescores_at || prev.prescores_at <= startedAt)) {
      next.prescores = prescores;
      next.prescores_at = startedAt;
    }
    if (profile && (!prev?.profile_at || prev.profile_at <= startedAt)) {
      next.profile = profile;
      next.profile_at = startedAt;
    }
    await db.snapshots.put(next);
  });
}

/** Refresh quietly: offline or not-yet-synced assessments simply keep their local copy. */
export async function tryRefreshAssessment(id: string, opts: { prescores?: boolean; profile?: boolean } = {}) {
  if (!isConnected()) return;
  // Not on the server until its create op syncs (the sync engine refreshes it right after).
  const creating = await db.outbox
    .where("assessment_id")
    .equals(id)
    .filter((o) => o.kind === "assessment.create")
    .count();
  if (creating > 0) return;
  try {
    await refreshAssessment(id, opts);
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 404)) console.info("refresh failed:", (e as Error).message);
  }
}

export interface ListRow extends AssessmentRow {
  local: boolean; // created on this device
  notSynced: boolean; // its assessment.create op has not been applied yet
}

export function useAssessmentList(): { rows: ListRow[]; updatedAt: string | null } | undefined {
  return useLive(async () => {
    const [cached, locals, ops] = await Promise.all([
      cacheGet(CACHE.assessments),
      db.assessments.toArray(),
      db.outbox.where("kind").equals("assessment.create").toArray(),
    ]);
    const pendingIds = new Set(ops.map((o) => o.assessment_id));
    const server = cached?.value ?? [];
    const seen = new Set(server.map((r) => r.id));
    const localIds = new Set(locals.map((l) => l.id));
    const rows: ListRow[] = server.map((r) => ({ ...r, local: localIds.has(r.id), notSynced: false }));
    for (const l of locals) {
      if (seen.has(l.id)) continue;
      const snap = await db.snapshots.get(l.id);
      rows.unshift({
        id: l.id,
        worker_code: l.worker_code,
        status: snap?.detail.assessment.status ?? "in_progress",
        is_sample: false,
        confirmed_nqr_id: snap?.detail.assessment.confirmed_nqr_id ?? null,
        created_at: l.created_at,
        local: true,
        notSynced: pendingIds.has(l.id) || !snap,
      });
    }
    return { rows, updatedAt: cached?.updated_at ?? null };
  }, []);
}

// ---- Assessment view = snapshot + pending outbox ops ----------------------------------------------

export const decisionKey = (taskId: string, criterionId: string) => `${taskId}|${criterionId}`;

export interface DecisionView {
  task_id: string;
  criterion_id: string;
  level: number | null; // null: accept queued offline, level known only after sync
  action: "accept" | "override";
  reason: string | null;
  assessor: string;
  created_at: string;
  pending: boolean;
  suggested_level: number | null;
}

export interface EvidenceView {
  key: string;
  task_id: string;
  photo_id: string;
  pending: boolean;
  /** Local thumbnail (a raw preview while queued, a blurred server copy after sync). */
  thumb: string | null;
  /** Server image URL (faces blurred), when synced. */
  imageUrl: string | null;
  server: EvidenceOut | null;
  created_at: string;
}

export interface AssessmentView {
  id: string;
  onServer: boolean;
  createPending: boolean;
  worker_id: string;
  worker_code: string;
  is_sample: boolean;
  status: string;
  signedOff: boolean;
  declaration_text: string;
  mapping: MappingResult | null;
  confirmed_nqr_id: number | null;
  confirmPending: boolean;
  checklist: Record<string, Record<string, boolean>>;
  /** `${task}|${item}` keys with a queued change. */
  checklistPending: Set<string>;
  decisions: Record<string, DecisionView>;
  evidence: EvidenceView[];
  signoff: Signoff | null;
  pendingOps: OutboxOp[];
  rejectedOps: number;
  /** Queued checklist/photo changes: server pre scores do not reflect them yet. */
  prescoreAffectingPending: number;
  decisionsPending: number;
  snapshot: Snapshot | null;
  created_at: string;
}

function decisionFromServer(d: Decision): DecisionView {
  return {
    task_id: d.task_id,
    criterion_id: d.criterion_id,
    level: d.final_level,
    action: d.action,
    reason: d.reason,
    assessor: d.assessor,
    created_at: d.created_at,
    pending: false,
    suggested_level: d.suggested_level,
  };
}

export async function loadAssessmentView(id: string): Promise<AssessmentView | null> {
  const [snap, local, ops, photos] = await Promise.all([
    db.snapshots.get(id),
    db.assessments.get(id),
    db.outbox.where("assessment_id").equals(id).sortBy("seq"),
    db.photos.where("assessment_id").equals(id).toArray(),
  ]);
  if (!snap && !local) return null;
  const d = snap?.detail;
  const view: AssessmentView = {
    id,
    onServer: !!snap,
    createPending: ops.some((o) => o.kind === "assessment.create"),
    worker_id: d?.assessment.worker_id ?? local?.worker_id ?? "",
    worker_code: d?.worker?.code ?? local?.worker_code ?? "?",
    is_sample: d?.assessment.is_sample ?? false,
    status: d?.assessment.status ?? "in_progress",
    signedOff: d?.assessment.status === "signed_off",
    declaration_text: d?.assessment.declaration_text ?? local?.declaration_text ?? "",
    mapping: d?.mapping ?? null,
    confirmed_nqr_id: d?.assessment.confirmed_nqr_id ?? null,
    confirmPending: false,
    checklist: {},
    checklistPending: new Set(),
    decisions: {},
    evidence: [],
    signoff: d?.signoff ?? null,
    pendingOps: ops,
    rejectedOps: ops.filter((o) => o.status === "rejected").length,
    prescoreAffectingPending: ops.filter((o) => o.kind === "checklist.set" || o.kind === "evidence.add").length,
    decisionsPending: ops.filter((o) => o.kind === "decision.add").length,
    snapshot: snap ?? null,
    created_at: d?.assessment.created_at ?? local?.created_at ?? "",
  };
  for (const [task, ticks] of Object.entries(d?.checklist ?? {})) view.checklist[task] = { ...ticks };
  for (const dec of d?.decisions ?? []) view.decisions[decisionKey(dec.task_id, dec.criterion_id)] = decisionFromServer(dec);

  // Overlay queued changes in replay order.
  for (const op of ops) {
    const p = op.payload;
    if (op.kind === "pack.confirm") {
      view.confirmed_nqr_id = Number(p.nqr_id);
      view.confirmPending = true;
    } else if (op.kind === "checklist.set") {
      const task = String(p.task_id);
      const ticks = (p.ticks ?? {}) as Record<string, boolean>;
      view.checklist[task] = { ...(view.checklist[task] ?? {}), ...ticks };
      for (const item of Object.keys(ticks)) view.checklistPending.add(`${task}|${item}`);
    } else if (op.kind === "decision.add") {
      const action = p.action === "override" ? "override" : "accept";
      view.decisions[decisionKey(String(p.task_id), String(p.criterion_id))] = {
        task_id: String(p.task_id),
        criterion_id: String(p.criterion_id),
        level: action === "override" ? Number(p.level) : ((op.meta?.shown_level as number | undefined) ?? null),
        action,
        reason: (p.reason as string | null | undefined) ?? null,
        assessor: String(p.assessor ?? ""),
        created_at: op.created_at,
        pending: true,
        suggested_level: (op.meta?.shown_level as number | undefined) ?? null,
      };
    }
  }

  // Evidence: server items, plus photos from this device that the snapshot does not show yet.
  const serverIds = new Set((d?.evidence ?? []).map((e) => e.id));
  const localByServerId = new Map(photos.filter((ph) => ph.server).map((ph) => [ph.server!.id, ph]));
  for (const e of d?.evidence ?? []) {
    view.evidence.push({
      key: `s${e.id}`,
      task_id: e.task_id,
      photo_id: e.photo_id,
      pending: false,
      thumb: localByServerId.get(e.id)?.thumb ?? null,
      imageUrl: apiUrl(e.image_url),
      server: e,
      created_at: e.created_at,
    });
  }
  for (const ph of photos) {
    if (ph.server && serverIds.has(ph.server.id)) continue;
    view.evidence.push({
      key: `l${ph.id}`,
      task_id: ph.task_id,
      photo_id: ph.photo_id,
      pending: ph.status === "queued",
      thumb: ph.thumb,
      imageUrl: ph.server ? apiUrl(ph.server.image_url) : null,
      server: ph.server,
      created_at: ph.created_at,
    });
  }
  return view;
}

export function useAssessmentView(id: string): AssessmentView | null | undefined {
  return useLive(() => loadAssessmentView(id), [id]);
}

/** Pending outbox + rating counts for the header. */
export function useQueueCounts(): { ops: number; rejected: number; ratings: number } | undefined {
  return useLive(async () => {
    const [ops, rejected, ratings] = await Promise.all([
      db.outbox.count(),
      db.outbox.where("status").equals("rejected").count(),
      db.ratings.count(),
    ]);
    return { ops, rejected, ratings };
  }, []);
}

/** The op that blocks the queue (the first one, when the server refused it). */
export function useBlockingOp(): OutboxOp | null | undefined {
  return useLive(async () => {
    const first = await db.outbox.orderBy("seq").first();
    return first && first.status === "rejected" ? first : null;
  }, []);
}

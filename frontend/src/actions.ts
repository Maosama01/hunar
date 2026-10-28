// Write side: every user action is stored locally and queued in the outbox (see sync.ts).
import { api, errorText, NetworkError, type RatingIn } from "./api";
import { db } from "./db";
import { addOp, enqueue, enqueueTick, requestSync } from "./sync";
import { isConnected } from "./status";
import { nowIso, uuid } from "./util";

/** New worker + assessment with the declaration. Ids are generated here so later ops (checklist,
 * photos, decisions) can reference them before the server has seen them. */
export async function createDeclaration(input: {
  code: string;
  preferred_language: "en" | "hi";
  declaration_text: string;
  actor: string;
}): Promise<string> {
  const workerId = uuid();
  const assessmentId = uuid();
  const t = nowIso();
  await db.transaction("rw", [db.workers, db.assessments, db.outbox], async () => {
    await db.workers.add({
      id: workerId,
      code: input.code,
      preferred_language: input.preferred_language,
      created_at: t,
      actor: input.actor,
    });
    await db.assessments.add({
      id: assessmentId,
      worker_id: workerId,
      worker_code: input.code,
      declaration_text: input.declaration_text,
      created_at: t,
      actor: input.actor,
    });
    await addOp(
      "worker.create",
      { id: workerId, code: input.code, preferred_language: input.preferred_language, actor: input.actor },
      { assessment_id: assessmentId },
    );
    await addOp(
      "assessment.create",
      { id: assessmentId, worker_id: workerId, declaration_text: input.declaration_text, actor: input.actor },
      { assessment_id: assessmentId },
    );
  });
  requestSync(0);
  return assessmentId;
}

export function setTick(assessmentId: string, taskId: string, itemId: string, value: boolean, actor: string) {
  return enqueueTick(assessmentId, taskId, itemId, value, actor);
}

export async function addPhoto(input: {
  assessmentId: string;
  taskId: string;
  photoId: string;
  imageB64: string;
  thumb: string;
  actor: string;
}): Promise<void> {
  const opId = uuid();
  await db.transaction("rw", [db.photos, db.outbox], async () => {
    await db.photos.add({
      id: opId,
      assessment_id: input.assessmentId,
      task_id: input.taskId,
      photo_id: input.photoId,
      thumb: input.thumb,
      thumb_kind: "local_raw",
      status: "queued",
      server: null,
      created_at: nowIso(),
    });
    await addOp(
      "evidence.add",
      {
        assessment_id: input.assessmentId,
        task_id: input.taskId,
        photo_id: input.photoId,
        image_b64: input.imageB64,
        consent_confirmed: true,
        actor: input.actor,
      },
      { op_id: opId },
    );
  });
  requestSync(0);
}

export function confirmPack(assessmentId: string, nqrId: number, reason: string | null, actor: string) {
  return enqueue("pack.confirm", { assessment_id: assessmentId, nqr_id: nqrId, actor, reason: reason || null });
}

export function decide(input: {
  assessmentId: string;
  taskId: string;
  criterionId: string;
  action: "accept" | "override";
  level: number | null;
  reason: string | null;
  assessor: string;
  shownLevel: number | null;
}) {
  const payload: Record<string, unknown> = {
    assessment_id: input.assessmentId,
    task_id: input.taskId,
    criterion_id: input.criterionId,
    action: input.action,
    reason: input.reason,
    assessor: input.assessor,
  };
  if (input.action === "override") payload.level = input.level;
  // The server recomputes the suggestion when it applies an accept; expected_level makes it refuse
  // the accept if that suggestion is no longer the one the assessor saw.
  if (input.action === "accept") payload.expected_level = input.shownLevel;
  return enqueue("decision.add", payload, { meta: { shown_level: input.shownLevel } });
}

/** Post a rating directly when online; otherwise keep it on the device and upload later. */
export async function submitRating(input: RatingIn): Promise<"sent" | "stored"> {
  // A stable client_id makes a retried upload idempotent on the server.
  const payload: RatingIn = { ...input, client_id: input.client_id ?? uuid() };
  if (isConnected()) {
    try {
      await api.addRating(payload);
      return "sent";
    } catch (e) {
      const error = e instanceof NetworkError ? null : errorText(e);
      await db.ratings.add({ payload, created_at: nowIso(), error });
      return "stored";
    }
  }
  await db.ratings.add({ payload, created_at: nowIso(), error: null });
  return "stored";
}

// IndexedDB schema (Dexie). Everything the user creates is written here first, so screens render
// offline; the outbox holds the writes that still have to reach the server, in order.
import Dexie, { type Table } from "dexie";
import type {
  AssessmentDetail,
  AssessmentRow,
  Condition,
  EvidenceOut,
  OpKind,
  PackSummary,
  PreScore,
  Profile,
  RatingIn,
  Rubrics,
  StudyItem,
} from "./api";

export type OpStatus = "pending" | "sending" | "rejected";

/** One queued write. `seq` (auto-increment) fixes the replay order. */
export interface OutboxOp {
  seq?: number;
  op_id: string;
  kind: OpKind;
  /** Exactly what POST /api/sync receives for this op. */
  payload: Record<string, unknown>;
  created_at: string;
  status: OpStatus;
  error: string | null;
  /** How many times this op was sent. An op that was sent once is never merged into again. */
  attempts: number;
  /** For overlays and per-assessment counts (not sent). */
  assessment_id: string | null;
  /** Client-only details for display (not sent), e.g. the suggested level the assessor accepted. */
  meta?: Record<string, unknown>;
}

/** A worker created on this device. */
export interface LocalWorker {
  id: string;
  code: string;
  preferred_language: string;
  created_at: string;
  actor: string;
}

/** An assessment created on this device (kept so it renders before and after sync). */
export interface LocalAssessment {
  id: string;
  worker_id: string;
  worker_code: string;
  declaration_text: string;
  created_at: string;
  actor: string;
}

/** Latest server copy of an assessment and its server-computed views. */
export interface Snapshot {
  id: string;
  detail: AssessmentDetail;
  fetched_at: string;
  prescores?: PreScore[];
  prescores_at?: string;
  profile?: Profile;
  profile_at?: string;
}

/** A photo captured on this device. The full-size image lives only in the outbox op payload and is
 * deleted with it once the server has applied the op (faces are blurred server side). `thumb` is a
 * small local preview until then; after sync it is replaced by a thumbnail of the blurred server copy. */
export interface LocalPhoto {
  id: string; // same as the op_id of its evidence.add op
  assessment_id: string;
  task_id: string;
  photo_id: string;
  thumb: string | null;
  thumb_kind: "local_raw" | "server_blurred" | null;
  status: "queued" | "synced";
  server: EvidenceOut | null;
  created_at: string;
}

export interface CacheRow<T = unknown> {
  key: string;
  value: T;
  updated_at: string;
}

export interface PendingRating {
  id?: number;
  payload: RatingIn;
  created_at: string;
  error: string | null;
}

export interface StudyProgress {
  key: string;
  rater_id: string;
  condition: Condition;
  session: number;
  include_sample: boolean;
  items: StudyItem[];
  index: number;
  rated: number;
  started_at: string;
  done: boolean;
}

class HunarDB extends Dexie {
  outbox!: Table<OutboxOp, number>;
  workers!: Table<LocalWorker, string>;
  assessments!: Table<LocalAssessment, string>;
  snapshots!: Table<Snapshot, string>;
  photos!: Table<LocalPhoto, string>;
  cache!: Table<CacheRow, string>;
  ratings!: Table<PendingRating, number>;
  studyProgress!: Table<StudyProgress, string>;

  constructor() {
    super("hunar");
    this.version(1).stores({
      outbox: "++seq, &op_id, kind, status, assessment_id",
      workers: "id, code",
      assessments: "id, worker_id, created_at",
      snapshots: "id",
      photos: "id, assessment_id, status",
      cache: "key",
      ratings: "++id",
      studyProgress: "key",
    });
  }
}

export const db = new HunarDB();

// Typed cache keys.
export const CACHE = {
  packs: "packs",
  rubrics: "rubrics",
  assessments: "assessments",
  workers: "workers",
} as const;

export interface CacheTypes {
  packs: PackSummary[];
  rubrics: Rubrics;
  assessments: AssessmentRow[];
  workers: { id: string; is_sample: boolean }[];
}

export async function cacheGet<K extends keyof CacheTypes>(key: K): Promise<CacheRow<CacheTypes[K]> | undefined> {
  return (await db.cache.get(key)) as CacheRow<CacheTypes[K]> | undefined;
}

export async function cachePut<K extends keyof CacheTypes>(key: K, value: CacheTypes[K]): Promise<void> {
  await db.cache.put({ key, value, updated_at: new Date().toISOString() });
}

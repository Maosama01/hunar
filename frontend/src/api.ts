// Typed client for the Hunar REST API (docs/api/openapi.json). All writes that can happen offline
// go through the outbox and POST /api/sync (see sync.ts); this module only talks HTTP.
import { setStatus } from "./status";

/** Same origin by default: Vite proxies /api to the FastAPI server. */
export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export const apiUrl = (path: string): string => `${API_BASE}${path}`;

// ---- Types (mirror backend/hunar/schemas.py, api/models.py and rubric/engine.py) ---------------

export type Lang = "en" | "hi";

export interface Bi {
  en: string;
  hi: string;
}

export interface Worker {
  id: string;
  code: string;
  preferred_language: string;
  is_sample: boolean;
  created_at: string;
}

export interface Assessment {
  id: string;
  worker_id: string;
  declaration_text: string;
  confirmed_nqr_id: number | null;
  status: string; // in_progress | signed_off
  is_sample: boolean;
  created_at: string;
}

export interface AssessmentRow {
  id: string;
  worker_code: string | null;
  status: string;
  is_sample: boolean;
  confirmed_nqr_id: number | null;
  created_at: string;
}

export interface EvidenceRef {
  sentence: string;
  similarity: number;
}

export interface CriterionMatch {
  pc_id: string;
  nos_code: string | null;
  text: string;
  score: number;
  evidence: EvidenceRef[];
}

export interface NOSCoverage {
  code: string | null;
  title: string;
  core: boolean | null;
  score: number;
  matched: number;
  total: number;
}

export interface PackScore {
  nqr_id: number;
  title: string;
  nsqf_level: number | null;
  rank: number;
  score: number;
  nos: NOSCoverage[];
  matched: CriterionMatch[];
  gaps: CriterionMatch[];
}

export interface MappingResult {
  method: string;
  sentences: string[];
  ranking: PackScore[];
  note: string;
}

export interface Detection {
  photo_id: string;
  cls: string;
  confidence: number;
  box?: number[];
}

export interface EvidenceOut {
  id: number;
  assessment_id: string;
  task_id: string;
  photo_id: string;
  sha256: string;
  faces_blurred: number;
  detector_status: string; // ok | unavailable
  detections: Detection[] | null;
  duplicate_of: number | null;
  duplicate_distance: number | null;
  consent_confirmed: boolean;
  created_at: string;
  image_url: string;
}

export interface Decision {
  id: number;
  assessment_id: string;
  task_id: string;
  criterion_id: string;
  suggested_level: number | null;
  final_level: number;
  action: "accept" | "override";
  reason: string | null;
  assessor: string;
  created_at: string;
}

export type Recommendation = "incomplete" | "not_yet_competent" | "recommend_for_certification";
export type Outcome = "not_yet_competent" | "recommend_for_certification";

export interface Signoff {
  assessor: string;
  agrees_with_tool: boolean;
  tool_recommendation: Recommendation;
  assessor_outcome: Outcome;
  comment: string;
  overall: number | null;
}

export interface AssessmentDetail {
  assessment: Assessment;
  worker: Worker | null;
  mapping: MappingResult | null;
  checklist: Record<string, Record<string, boolean>>;
  evidence: EvidenceOut[];
  decisions: Decision[];
  signoff: Signoff | null;
}

export interface PackSummary {
  nqr_id: number;
  title: string;
  nsqf_level: number | null;
  sector: string | null;
  role: string;
  nqr_code: string | null;
  n_nos: number;
  n_pcs: number;
}

export interface LabelledItem {
  id: string;
  en: string;
  hi: string;
}

export interface Criterion {
  id: string;
  nos: string;
  pc_refs: string[];
  weight: number;
  critical: boolean;
  text: Bi;
  checklist: string[];
  cv_classes: string[];
  cv_classes_any: string[];
  levels: Record<string, string>;
}

export interface Task {
  task_id: string;
  qualification_nqr_id: number;
  title: Bi;
  instructions: Bi;
  photos: LabelledItem[];
  checklist: LabelledItem[];
  criteria: Criterion[];
}

export interface Rubrics {
  levels: Record<string, Bi>;
  pass_mark: number;
  tasks: Task[];
}

export interface PreScore {
  task_id: string;
  criterion_id: string;
  suggested_level: number | null;
  confidence: "none" | "low" | "medium" | "high";
  reasons: string[];
  conflict: boolean;
}

export interface NOSResult {
  nos: string;
  score: number;
  criteria: number;
  below_competent: number;
}

export interface Gap {
  task_id: string;
  criterion_id: string;
  nos: string;
  level: number;
  critical: boolean;
  text: string;
}

export interface Profile {
  overall: number | null;
  pass_mark: number;
  nos: NOSResult[];
  gaps: Gap[];
  critical_failures: Gap[];
  unscored: string[];
  recommendation: Recommendation;
  explanation: string;
  requires_assessor_signoff: boolean;
}

export interface AuditEntry {
  seq: number;
  ts: string;
  actor: string;
  action: string;
  subject: string;
  payload_json: string;
  prev_hash: string;
  hash: string;
}

export interface VerifyResult {
  ok: boolean;
  entries: number;
  head?: string;
  first_bad_seq?: number;
}

export interface StudyItem {
  position: number;
  item_id: string;
  image_url: string;
  is_sample: boolean;
  task_title: Bi;
  criterion: Bi;
  level_names: Record<string, Bi>;
  anchors?: Record<string, string>;
  prescore?: PreScore | null;
}

export type Condition = "unassisted" | "assisted";

export interface RatingIn {
  rater_id: string;
  item_id: string;
  condition: Condition;
  session: number;
  position: number;
  level: number;
  seconds: number | null;
}

export type OpKind =
  | "worker.create"
  | "assessment.create"
  | "pack.confirm"
  | "checklist.set"
  | "evidence.add"
  | "decision.add";

export interface SyncOpIn {
  op_id: string;
  kind: OpKind;
  payload: Record<string, unknown>;
}

export interface SyncResult {
  op_id: string;
  status: "applied" | "duplicate" | "rejected";
  result?: unknown;
  error?: unknown;
}

export interface Health {
  status: string;
  detector: { available: boolean; reason?: string; note?: string };
  mapper: string;
  principle: string;
}

// ---- Errors -------------------------------------------------------------------------------------

/** The server could not be reached (offline, timeout, or the dev proxy reports the API is down). */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

/** The server answered with an error status. `detail` is FastAPI's error detail. */
export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(detailText(detail) || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Human readable text for a FastAPI `detail` (a string, or a list of pydantic errors). */
export function detailText(detail: unknown): string {
  if (detail === null || detail === undefined) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === "object" && "msg" in d) {
          const loc = Array.isArray((d as { loc?: unknown[] }).loc) ? (d as { loc: unknown[] }).loc.join(".") : "";
          return `${loc ? `${loc}: ` : ""}${String((d as { msg: unknown }).msg)}`;
        }
        return JSON.stringify(d);
      })
      .join("; ");
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError || e instanceof NetworkError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}

// ---- Transport ----------------------------------------------------------------------------------

interface RequestOpts {
  timeoutMs?: number;
}

async function request<T>(method: string, path: string, body?: unknown, opts: RequestOpts = {}): Promise<T> {
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 15000);
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
      cache: "no-store",
    });
  } catch (e) {
    setStatus({ reachable: false });
    const aborted = e instanceof DOMException && e.name === "AbortError";
    throw new NetworkError(aborted ? "the server did not answer in time" : "no connection to the server");
  } finally {
    window.clearTimeout(timer);
  }
  const text = await res.text().catch(() => "");
  if (!res.ok) {
    // 502-504, or the Vite dev/preview proxy's empty 500, mean the API itself is down.
    if ((res.status >= 502 && res.status <= 504) || (res.status === 500 && !text)) {
      setStatus({ reachable: false });
      throw new NetworkError(`the server is not reachable (HTTP ${res.status})`);
    }
    setStatus({ reachable: true });
    let detail: unknown = text;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      detail = parsed.detail ?? parsed;
    } catch {
      /* plain text */
    }
    throw new ApiError(res.status, detail);
  }
  setStatus({ reachable: true });
  return (text ? JSON.parse(text) : undefined) as T;
}

const get = <T>(path: string, opts?: RequestOpts) => request<T>("GET", path, undefined, opts);
const post = <T>(path: string, body: unknown, opts?: RequestOpts) => request<T>("POST", path, body, opts);

const q = (params: Record<string, string | number | boolean | undefined>) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");

// ---- Endpoints ----------------------------------------------------------------------------------

export const api = {
  health: () => get<Health>("/api/health", { timeoutMs: 5000 }),
  packs: () => get<PackSummary[]>("/api/packs"),
  rubrics: () => get<Rubrics>("/api/rubrics"),
  assessments: () => get<AssessmentRow[]>("/api/assessments"),
  workers: () => get<Worker[]>("/api/workers"),
  assessment: (id: string) => get<AssessmentDetail>(`/api/assessments/${encodeURIComponent(id)}`),
  prescores: (id: string) => get<PreScore[]>(`/api/assessments/${encodeURIComponent(id)}/prescores`),
  profile: (id: string) => get<Profile>(`/api/assessments/${encodeURIComponent(id)}/profile`),
  signoff: (id: string, body: { assessor: string; agrees: boolean; outcome: Outcome | null; comment: string }) =>
    post<{ id: string; status: string; signoff: Signoff }>(`/api/assessments/${encodeURIComponent(id)}/signoff`, body),
  audit: (params: { limit?: number; subject?: string }) => get<AuditEntry[]>(`/api/audit?${q(params)}`),
  auditVerify: () => get<VerifyResult>("/api/audit/verify"),
  sync: (ops: SyncOpIn[]) => post<{ results: SyncResult[] }>("/api/sync", { ops }, { timeoutMs: 90000 }),
  studyItems: (params: { rater_id: string; condition: Condition; include_sample: boolean }) =>
    get<StudyItem[]>(`/api/study/items?${q(params)}`),
  addRating: (body: RatingIn) => post<unknown>("/api/study/ratings", body),
};

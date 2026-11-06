// Typed client for the Hunar REST API (docs/api/openapi.json). All writes that can happen offline
// go through the outbox and POST /api/sync (see sync.ts); this module only talks HTTP.
import type { LangCode } from "./i18n/languages";
import { clearSession, getToken } from "./session";
import { setStatus } from "./status";

/** Same origin by default: Vite proxies /api to the FastAPI server. */
export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export const apiUrl = (path: string): string => `${API_BASE}${path}`;

// ---- Types (mirror backend/hunar/schemas.py, api/models.py and rubric/engine.py) ---------------

/** Any of the 23 app language codes. */
export type Lang = LangCode;

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
  /** Selects the rubric tasks and qualification packs; older cached copies lack it (electrician). */
  trade?: string;
  declaration_text: string;
  confirmed_nqr_id: number | null;
  status: string; // in_progress | signed_off
  is_sample: boolean;
  created_at: string;
}

export interface AssessmentRow {
  id: string;
  worker_code: string | null;
  trade?: string;
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
  /** Should be an int; the current backend can return it as an 8-byte little-endian blob string
   * (numpy int64 stored in SQLite). Read it with intFromApi(). */
  duplicate_distance: number | string | null;
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
  clips?: GuidedClipOut[];
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
  /** "electrician" for the M1 packs; plumber and carpenter for their own qualification files. */
  trade?: string;
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
  /** Video pilot: the guided clip and the aspects (name, function, failure, test) this criterion uses. */
  clip?: { id: string; aspects: string[]; meter: boolean } | null;
  levels: Record<string, string>;
}

/** One guided clip the app asks for (video pilot): show one part and explain it. */
export interface ClipPrompt {
  id: string;
  part: Bi;
  prompt: Bi;
  detect: string[];
  terms: Record<string, string[]>;
  meter: { quantity: string; unit: string } | null;
}

/** A stored guided clip: faces blurred, sound removed; the transcript is a draft. */
export interface GuidedClipOut {
  id: string;
  assessment_id: string;
  task_id: string;
  clip_id: string;
  duration_s: number;
  frames_with_faces: number;
  detector: string;
  part_seen: boolean | null;
  hand_on_part: boolean | null;
  /** About one frame a second: when the part was seen (best confidence) and whether a hand was on it. */
  frames?: { t: number; part: number | null; hand_on_part: boolean }[];
  meter_value: number | null;
  printed_value: number | null;
  tolerance_pct: number | null;
  meter_in_range: boolean | null;
  transcript: { text: string; words?: { word: string; start: number; end?: number }[]; unavailable?: string };
  found: Record<string, [string, number][]>;
  video_url: string;
  created_at: string;
}

export interface Task {
  task_id: string;
  trade?: string;
  qualification_nqr_id: number;
  /** Who wrote the rubric and which review is still pending. */
  review?: Bi | null;
  title: Bi;
  instructions: Bi;
  photos: LabelledItem[];
  checklist: LabelledItem[];
  clips?: ClipPrompt[];
  criteria: Criterion[];
}

export interface Rubrics {
  levels: Record<string, Bi>;
  pass_mark: number;
  pass_rules?: Record<string, { aggregate: number; nos: number | null }>;
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
  /** Set when the qualification file also needs this score in every NOS (carpenter). */
  nos_pass_mark?: number | null;
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
  client_id?: string;
}

export type OpKind =
  | "worker.create"
  | "assessment.create"
  | "pack.confirm"
  | "checklist.set"
  | "evidence.add"
  | "decision.add";

export interface Transcript {
  text: string;
  language: string;
  duration_s: number;
  model: string;
  note: string;
}

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
  speech?: { available: boolean; reason?: string; model?: string; note?: string };
  bhashini?: { configured: boolean };
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

/** An integer from the API that may arrive as a number, a numeric string, or a little-endian byte
 * string (see EvidenceOut.duplicate_distance). Returns null when it cannot be read. */
export function intFromApi(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v !== "string" || v.length === 0) return null;
  if (/^-?\d+$/.test(v.trim())) return Number(v.trim());
  if (v.length <= 8 && [...v].every((c) => c.charCodeAt(0) < 256)) {
    let n = 0;
    for (let i = v.length - 1; i >= 0; i--) n = n * 256 + v.charCodeAt(i);
    return Number.isSafeInteger(n) ? n : null;
  }
  return null;
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
  const token = getToken();
  try {
    const form = body instanceof FormData;
    const headers: Record<string, string> = {};
    if (body !== undefined && !form) headers["Content-Type"] = "application/json";
    if (token) headers.Authorization = `Bearer ${token}`;
    res = await fetch(apiUrl(path), {
      method,
      headers,
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
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
    // A token the server no longer accepts (expired, logged out elsewhere, PIN reset): end the
    // session here; the guards send the person to the login screen. Queued changes stay in Dexie.
    if (res.status === 401 && token && token === getToken() && !path.startsWith("/api/auth/login")) {
      clearSession("expired");
    }
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
const put = <T>(path: string, body: unknown, opts?: RequestOpts) => request<T>("PUT", path, body, opts);
const del = <T>(path: string, opts?: RequestOpts) => request<T>("DELETE", path, undefined, opts);
const patch = <T>(path: string, body: unknown, opts?: RequestOpts) => request<T>("PATCH", path, body, opts);
const enc = encodeURIComponent;

/** Fetch an API resource that needs the login (e.g. evidence images) as a Blob. */
export async function fetchBlob(path: string): Promise<Blob | null> {
  const token = getToken();
  try {
    const res = await fetch(path.startsWith("http") ? path : apiUrl(path), {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (res.status === 401 && token && token === getToken()) clearSession("expired");
    return res.ok ? await res.blob() : null;
  } catch {
    return null;
  }
}

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
  /** Video pilot: upload one guided clip. The server blurs faces, drops the sound and transcribes it. */
  addClip: (assessmentId: string, f: { taskId: string; clipId: string; video: Blob; language: string;
    reading?: number; printed?: number; tolerancePct?: number }) => {
    const form = new FormData();
    form.append("task_id", f.taskId);
    form.append("clip_id", f.clipId);
    form.append("consent_confirmed", "true");
    form.append("language", f.language);
    if (f.reading !== undefined) form.append("reading", String(f.reading));
    if (f.printed !== undefined) form.append("printed", String(f.printed));
    if (f.tolerancePct !== undefined) form.append("tolerance_pct", String(f.tolerancePct));
    form.append("file", f.video, f.video.type.includes("mp4") ? "clip.mp4" : "clip.webm");
    return post<GuidedClipOut>(`/api/assessments/${enc(assessmentId)}/clips`, form, { timeoutMs: 300000 });
  },
  /** Draft transcript of a recording; the server does not keep the audio. The first call loads the model. */
  transcribe: (audio: Blob, language: string) => {
    const form = new FormData();
    const ext = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
    form.append("file", audio, `declaration.${ext}`);
    form.append("language", language);
    return post<Transcript>("/api/transcribe", form, { timeoutMs: 180000 });
  },

  // ---- accounts (/api/auth) ----
  authConfig: () => get<AuthConfig>("/api/auth/config"),
  requestOtp: (phone: string, purpose: "register" | "reset") => post<OtpOut>("/api/auth/otp", { phone, purpose }),
  register: (body: RegisterIn) => post<RegisterOut>("/api/auth/register", body),
  login: (phone: string, pin: string) => post<AuthOut>("/api/auth/login", { phone, pin }),
  logout: () => post<{ ok: boolean }>("/api/auth/logout", {}, { timeoutMs: 5000 }),
  me: () => get<Account>("/api/auth/me"),
  resetPin: (body: { phone: string; new_pin: string; otp_challenge_id: string; otp_code: string }) =>
    post<{ ok: boolean }>("/api/auth/reset-pin", body),
  setConsent: (purpose: string, granted: boolean) => post<Account>("/api/auth/consents", { purpose, granted }),
  eraseMe: () => del<{ erased: boolean }>("/api/auth/me"),
  updateMe: (body: { language?: string; display_name?: string }) => patch<Account>("/api/auth/me", body),

  // ---- marketplace ----
  trades: () => get<TradesOut>("/api/trades"),
  myProfile: () => get<MyProfile | null>("/api/me/profile"),
  saveProfile: (body: ProfileIn) => put<MyProfile>("/api/me/profile", body),
  searchWorkers: (p: { trade?: string; pincode?: string; assessed_only?: boolean; permit_only?: boolean }) =>
    get<PublicProfile[]>(`/api/market/workers?${q(p)}`),
  publicWorker: (id: string) => get<PublicProfile>(`/api/market/workers/${enc(id)}`),
  book: (body: BookingIn) => post<Booking>("/api/bookings", body),
  bookings: () => get<Booking[]>("/api/bookings"),
  bookingAction: (id: string, action: "accept" | "decline" | "cancel" | "complete") =>
    post<Booking>(`/api/bookings/${enc(id)}/${action}`, {}),
  rateBooking: (id: string, stars: number, review: string) =>
    post<Booking>(`/api/bookings/${enc(id)}/rate`, { stars, review }),
  requestAssessment: (body: { declaration_text: string; preferred_date: string | null }) =>
    post<AssessmentRequest>("/api/assessment-requests", body),
  assessmentRequests: () => get<AssessmentRequest[]>("/api/assessment-requests"),
  startRequest: (id: string) =>
    post<{ request: AssessmentRequest; assessment_id: string }>(`/api/assessment-requests/${enc(id)}/start`, {}),
  cancelRequest: (id: string) => post<AssessmentRequest>(`/api/assessment-requests/${enc(id)}/cancel`, {}),
  adminWorkers: (p: { trade?: string }) =>
    get<(PublicProfile & { visible: boolean; phone_masked: string })[]>(`/api/admin/workers?${q(p)}`),
  setPermit: (accountId: string, status: PermitStatus, state: string) =>
    post<unknown>(`/api/admin/workers/${enc(accountId)}/permit`, { status, state }),

  // ---- quiz ----
  quizBanks: () => get<Record<string, QuizBank>>("/api/quiz/banks"),
  startQuiz: (trade: string, language: string) => post<{ attempt_id: string; item: QuizItem }>("/api/quiz/attempts", { trade, language }),
  answerQuiz: (attemptId: string, body: { item_id: string; choice: number | null; seconds: number | null }) =>
    post<QuizAnswerOut>(`/api/quiz/attempts/${enc(attemptId)}/answers`, body),
  quizAttempts: () => get<QuizAttemptRow[]>("/api/quiz/attempts"),
  quizAttempt: (id: string) => get<QuizAttemptOut>(`/api/quiz/attempts/${enc(id)}`),
  quizReview: (id: string) => get<QuizReviewItem[]>(`/api/quiz/attempts/${enc(id)}/review`),
};

// ---- Accounts, marketplace and quiz types (backend/hunar/accounts, market, quiz) ----------------

export type AccountRole = "worker" | "customer" | "facilitator" | "assessor" | "admin";

export interface Account {
  id: string;
  role: AccountRole;
  display_name: string;
  language: string;
  phone_masked: string;
  phone_verified: boolean;
  is_sample: boolean;
  consents: Record<string, boolean>;
  /** Workers only: the compulsory quiz. Until one is finished the app shows nothing but the quiz. */
  quiz?: QuizGate;
}

export interface QuizGate {
  done: boolean;
  /** Trades with a finished quiz that counts (at least half the answers at reading pace). */
  counted_trades: Trade[];
  in_progress: { attempt_id: string; trade: Trade } | null;
}

export interface AuthOut {
  token: string;
  account: Account;
}

/** A new worker's first quiz starts with the account. */
export interface RegisterOut extends AuthOut {
  quiz?: { attempt_id: string; item: QuizItem };
}

export interface Purpose {
  roles: string[];
  required: boolean;
  data: string[];
  why: string;
  withdraw: string;
}

export interface AuthConfig {
  otp_required: boolean;
  otp_provider: string | null;
  languages: string[];
  notice_version: string;
  purposes: Record<string, Record<string, Purpose>>;
  pin_rules: string;
}

export interface OtpOut {
  otp_required: boolean;
  challenge_id?: string;
  expires_in_minutes?: number;
  test_code?: string;
  test_note?: string;
}

export interface RegisterIn {
  phone: string;
  pin: string;
  role: "worker" | "customer";
  display_name: string;
  language: string;
  is_adult: boolean;
  consents: Record<string, boolean>;
  /** Workers only: the trade of the quiz that starts right after registering. */
  trade?: Trade;
  otp_challenge_id?: string;
  otp_code?: string;
}

export type Trade = "electrician" | "plumber" | "carpenter";
export const TRADES: Trade[] = ["electrician", "plumber", "carpenter"];

export interface Job {
  en: string;
  hi: string;
  needs_permit: boolean;
}

export interface QualificationRef {
  nqr_id: number;
  title: string;
  nsqf_level: number | null;
  awarding_body: string | null;
}

export interface TradeInfo {
  name: Bi;
  qualification: QualificationRef | null;
  /** Whether the assessor flow has practical tasks for this trade (electricians only so far). */
  practical_assessment: boolean;
  jobs: Record<string, Job>;
}

export type TradesOut = Record<string, TradeInfo> & { _permit_note?: string; _practical_note?: string };

export type PermitStatus = "none" | "self_declared" | "document_checked";

export interface Badge {
  kind: "skill_assessed" | "permit_checked";
  qualification?: QualificationRef | null;
  assessment_id?: string;
  state?: string;
  date: string | null;
  note: string;
}

export interface PublicProfile {
  account_id: string;
  display_name: string;
  trade: Trade;
  trade_name: Bi | null;
  years_experience: number;
  district: string;
  pincode_area: string;
  languages: string[];
  bio: string;
  badges: Badge[];
  skill_assessed: boolean;
  permit: { status: PermitStatus; state: string };
  rating: { average: number | null; count: number };
  is_sample: boolean;
}

export interface ProfileIn {
  trade: Trade;
  years_experience: number;
  pincode: string;
  district: string;
  languages: string[];
  bio: string;
  permit_status: "none" | "self_declared";
  permit_state: string;
}

export interface MyProfile {
  account_id: string;
  trade: Trade;
  years_experience: number;
  pincode: string;
  district: string;
  languages: string; // comma-separated codes
  bio: string;
  visible: boolean;
  permit_status: PermitStatus;
  permit_state: string;
  permit_checked_at: string | null;
  updated_at: string;
  public: PublicProfile;
  visible_reason: string | null;
}

export type Slot = "morning" | "afternoon" | "evening";

export interface BookingIn {
  worker_id: string;
  job_type: string;
  description: string;
  pincode: string;
  preferred_date: string;
  slot: Slot;
}

export type BookingStatus = "requested" | "accepted" | "declined" | "cancelled" | "completed";

export interface Booking {
  id: string;
  customer_id: string;
  worker_id: string;
  trade: Trade;
  job_type: string;
  description: string;
  pincode: string;
  preferred_date: string;
  slot: Slot;
  status: BookingStatus;
  rating: number | null;
  review: string;
  created_at: string;
  updated_at: string;
  other_party: { account_id: string; display_name: string; role: "worker" | "customer"; phone?: string };
  job: Job | null;
  you_are: "customer" | "worker";
}

export interface QuizSummary extends QuizResult {
  attempts_finished: number;
  /** Finished quizzes that did not count because too many answers were too quick. */
  attempts_not_counted: number;
}

export interface AssessmentRequest {
  id: string;
  account_id: string;
  trade: Trade;
  declaration_text: string;
  pincode: string;
  preferred_date: string | null;
  status: "open" | "started" | "cancelled";
  assessor_account_id: string | null;
  assessment_id: string | null;
  created_at: string;
  worker_display_name?: string | null;
  quiz?: QuizSummary | null;
}

export interface QuizBank {
  version: string;
  status: string;
  n_items: number;
  qualification_nqr_id: number | null;
  calibrated: boolean;
  nos: Record<string, { title: Bi; weight: number }>;
  languages: { original: string[]; machine_translated: string[] };
  rules: { min_items: number; max_items: number; se_target: number; min_read_share: number };
}

export type TranslationStatus = "original" | "machine" | "reviewed" | "missing";

export interface QuizItem {
  id: string;
  position: number;
  nos: string;
  nos_title: Bi;
  stem: string;
  options: string[];
  image: string | null;
  language: string;
  translation: TranslationStatus;
  max_items: number;
}

export interface NosResult {
  nos: string;
  title: Bi;
  answered: number;
  correct: number;
  enough: boolean;
}

export interface QuizResult {
  attempt_id: string;
  trade: Trade;
  status: string;
  started_at: string;
  finished_at: string | null;
  theta: number;
  sd: number;
  expected_percent: number;
  expected_percent_interval90: [number, number];
  n_answered: number;
  n_scored: number;
  n_rapid: number;
  n_dont_know: number;
  by_nos: NosResult[];
  revise: NosResult[];
  /** Share of answers given at reading pace; the quiz counts only if it is at least min_read_share. */
  read_share: number;
  min_read_share: number;
  counts: boolean;
  bank: { version: string; status: string; params_version: string; calibrated: boolean };
  calibration_note: string | null;
  note: string;
}

export type QuizAnswerOut =
  | { done: false; item: QuizItem; rapid_warning: boolean }
  | { done: true; result: QuizResult };

export type QuizAttemptOut = { done: false; item: QuizItem } | { done: true; result: QuizResult };

export type QuizAttemptRow =
  | QuizResult
  | { attempt_id: string; trade: Trade; status: "in_progress"; n_answered: number };

export interface QuizReviewItem {
  position: number;
  stem: string;
  options: string[];
  your_choice: number | null;
  answer: number;
  correct: boolean;
  rapid: boolean;
  explanation: string;
  sources: string[];
  translation: TranslationStatus;
}

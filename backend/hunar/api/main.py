"""Hunar REST API (FastAPI). Run: `make api` -> http://localhost:8000/docs"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from hunar.accounts import auth
from hunar.accounts.models import Account
from hunar.accounts.routes import router as accounts_router
from hunar.api import services as svc
from hunar.api.db import get_session, init_db
from hunar.api.models import AppliedOp, Assessment, AuditEntry, EvidenceItem, StudyItem, StudyRating, Worker
from hunar.audit import log as audit
from hunar.evidence import detector
from hunar.market.routes import router as market_router
from hunar.paths import DATA
from hunar.quiz.routes import router as quiz_router
from hunar.rubric import engine
from hunar.schemas import MappingResult
from hunar.speech import bhashini
from hunar.speech import transcribe as speech


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Hunar API", version="0.1.0", lifespan=lifespan,
              description="AI assisted RPL for domestic electricians. AI suggests; the assessor decides.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DB = Depends(get_session)
for _r in (accounts_router, market_router, quiz_router):
    app.include_router(_r)
# Assessor-side work needs a staff account; decisions that affect a worker's result need an assessor.
STAFF = Depends(auth.require_roles("facilitator", "assessor", "admin"))
ASSESSOR = Depends(auth.require_roles("assessor", "admin"))


# ---- Request bodies ---------------------------------------------------------------------------


class MapIn(BaseModel):
    text: str = Field(min_length=3)


class WorkerIn(BaseModel):
    id: str | None = None
    code: str = Field(min_length=1, max_length=32)
    preferred_language: Literal["en", "hi"] = "hi"
    actor: str = "facilitator"


class AssessmentIn(BaseModel):
    id: str | None = None
    worker_id: str
    declaration_text: str = ""
    actor: str = "facilitator"


class ConfirmPackIn(BaseModel):
    nqr_id: int
    actor: str
    reason: str | None = None


class ChecklistIn(BaseModel):
    task_id: str
    ticks: dict[str, bool]
    actor: str


class DecisionIn(BaseModel):
    task_id: str
    criterion_id: str
    action: Literal["accept", "override"]
    level: int | None = None
    reason: str | None = None
    assessor: str
    expected_level: int | None = Field(default=None, description="For accept: the suggestion the assessor saw")


class SignoffIn(BaseModel):
    assessor: str
    agrees: bool
    outcome: Literal["not_yet_competent", "recommend_for_certification"] | None = None
    comment: str = ""


class SyncOp(BaseModel):
    op_id: str
    kind: Literal["worker.create", "assessment.create", "pack.confirm", "checklist.set", "evidence.add",
                  "decision.add"]
    payload: dict


class SyncIn(BaseModel):
    ops: list[SyncOp]


class RatingIn(BaseModel):
    rater_id: str = Field(min_length=1)
    item_id: str
    condition: Literal["unassisted", "assisted"]
    session: int = Field(ge=1)
    position: int = Field(ge=0)
    level: int = Field(ge=0, le=3)
    seconds: float | None = None
    client_id: str | None = Field(default=None, max_length=64, description="Idempotency key for retries")


# ---- Reference data -----------------------------------------------------------------------------


@app.get("/api/health")
def health():
    # Polled often by every open app: it must stay cheap and never load a model.
    return {"status": "ok", "detector": detector.status(), "speech": speech.status(),
            "bhashini": {"configured": bhashini.Bhashini.from_env() is not None},
            "mapper": svc.mapper_name(), "principle": "AI suggests, the assessor decides."}


@app.get("/api/packs")
def packs():
    return [{"nqr_id": p.nqr_id, "title": p.title, "nsqf_level": p.nsqf_level, "sector": p.sector, "role": p.role,
             "nqr_code": p.nqr_code, "n_nos": len(p.nos), "n_pcs": len(p.criteria()), "source": p.source}
            for p in svc.mapper().packs]


@app.get("/api/packs/{nqr_id}")
def pack(nqr_id: int):
    for p in svc.mapper().packs:
        if p.nqr_id == nqr_id:
            return p
    raise HTTPException(404, "pack not found")


@app.post("/api/map", response_model=MappingResult)
def map_declaration(body: MapIn):
    return svc.mapper().map(body.text)


@app.post("/api/transcribe")
def transcribe(language: str | None = Form(None), file: UploadFile = File(...),
               _acc: Account = Depends(auth.current_account)):
    """Draft transcript of a spoken declaration. The audio is not stored."""
    if not speech.available():
        raise HTTPException(503, "voice input is not installed on this server (make voice); please type instead")
    data = file.file.read(speech.MAX_BYTES + 1)
    if not data:
        raise HTTPException(422, "empty audio")
    if len(data) > speech.MAX_BYTES:
        raise HTTPException(413, "recording too long; please record a shorter part")
    try:
        return speech.transcribe_bytes(data, speech.whisper_language(language), file.filename or "")
    except Exception as e:  # undecodable audio, or the model could not be downloaded while offline
        raise HTTPException(422, f"could not transcribe the recording: {type(e).__name__}") from e


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    language: str


@app.post("/api/tts")
def tts(body: TtsIn, _acc: Account | None = Depends(auth.optional_account)):
    """Read text aloud with Bhashini TTS (server-side keys). WAV, cached by language and text."""
    if body.language not in bhashini.LANGS:
        raise HTTPException(422, f"unknown language {body.language!r}")
    cache = DATA / "tts_cache" / f"{hashlib.sha256(f'{body.language}|{body.text}'.encode()).hexdigest()}.wav"
    if not cache.exists():
        client = bhashini.Bhashini.from_env()
        if client is None:
            raise HTTPException(503, "read-aloud by Bhashini is not set up on this server")
        try:
            audio = client.tts(body.text, body.language)
        except Exception as e:  # network, quota or unsupported language
            raise HTTPException(502, f"Bhashini TTS failed: {type(e).__name__}") from e
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(audio)
    return Response(cache.read_bytes(), media_type="audio/wav")


@app.get("/api/rubrics")
def rubrics():
    return {"levels": engine.LEVEL_NAMES, "pass_mark": engine.DEFAULT_PASS_MARK,
            "tasks": [t.model_dump() for t in engine.load_tasks()]}


# ---- Workers and assessments ---------------------------------------------------------------------


@app.post("/api/workers", response_model=Worker)
def create_worker(body: WorkerIn, acc: Account = STAFF, s: Session = DB):
    return svc.create_worker(s, body.code, body.preferred_language, auth.actor(acc), body.id)


@app.get("/api/workers", response_model=list[Worker])
def list_workers(_acc: Account = STAFF, s: Session = DB):
    return list(s.exec(select(Worker).order_by(Worker.created_at)))


@app.post("/api/assessments")
def create_assessment(body: AssessmentIn, acc: Account = STAFF, s: Session = DB):
    return svc.create_assessment(s, body.worker_id, body.declaration_text, auth.actor(acc), body.id)


@app.get("/api/assessments")
def list_assessments(_acc: Account = STAFF, s: Session = DB):
    out = []
    for a in s.exec(select(Assessment).order_by(Assessment.created_at.desc())):
        w = s.get(Worker, a.worker_id)
        out.append({"id": a.id, "worker_code": w.code if w else None, "status": a.status, "is_sample": a.is_sample,
                    "confirmed_nqr_id": a.confirmed_nqr_id, "created_at": a.created_at})
    return out


@app.get("/api/assessments/{aid}")
def get_assessment(aid: str, _acc: Account = STAFF, s: Session = DB):
    a = svc.get_or_404(s, Assessment, aid)
    dec = svc.latest_decisions(s, aid)
    return {
        "assessment": a.model_dump(exclude={"mapping_json", "signoff_json"}),
        "worker": s.get(Worker, a.worker_id),
        "mapping": json.loads(a.mapping_json) if a.mapping_json else None,
        "checklist": svc.checklist_for(s, aid),
        "evidence": [_evidence_out(e) for e in svc.evidence_for(s, aid)],
        "decisions": [d.model_dump() for d in dec.values()],
        "signoff": json.loads(a.signoff_json) if a.signoff_json else None,
    }


@app.post("/api/assessments/{aid}/confirm-pack")
def confirm_pack(aid: str, body: ConfirmPackIn, acc: Account = ASSESSOR, s: Session = DB):
    a = svc.confirm_pack(s, svc.get_or_404(s, Assessment, aid), body.nqr_id, auth.actor(acc), body.reason)
    return {"id": a.id, "confirmed_nqr_id": a.confirmed_nqr_id}


@app.put("/api/assessments/{aid}/checklist")
def set_checklist(aid: str, body: ChecklistIn, acc: Account = STAFF, s: Session = DB):
    return svc.set_checklist(s, svc.get_or_404(s, Assessment, aid), body.task_id, body.ticks, auth.actor(acc))


def _evidence_out(e: EvidenceItem) -> dict:
    d = e.model_dump(exclude={"stored_path", "detections_json"})
    d["detections"] = json.loads(e.detections_json) if e.detections_json else None
    d["image_url"] = f"/api/evidence/{e.id}/image"
    return d


@app.post("/api/assessments/{aid}/evidence")
async def add_evidence(aid: str, task_id: str = Form(...), photo_id: str = Form(...),
                       consent_confirmed: bool = Form(False), actor: str = Form("facilitator"),
                       file: UploadFile = File(...), acc: Account = STAFF, s: Session = DB):
    a = svc.get_or_404(s, Assessment, aid)
    ev = svc.add_evidence(s, a, task_id, photo_id, await file.read(), consent_confirmed, auth.actor(acc))
    return _evidence_out(ev)


@app.get("/api/evidence/{eid}/image")
def evidence_image(eid: int, _acc: Account = STAFF, s: Session = DB):
    e = svc.get_or_404(s, EvidenceItem, eid)
    return FileResponse(DATA / e.stored_path, media_type="image/jpeg")


@app.get("/api/assessments/{aid}/prescores", response_model=list[engine.PreScore])
def prescores(aid: str, _acc: Account = STAFF, s: Session = DB):
    return svc.prescores(s, svc.get_or_404(s, Assessment, aid))


@app.post("/api/assessments/{aid}/decisions")
def decide(aid: str, body: DecisionIn, acc: Account = ASSESSOR, s: Session = DB):
    a = svc.get_or_404(s, Assessment, aid)
    return svc.decide(s, a, body.task_id, body.criterion_id, body.action, body.level, body.reason, auth.actor(acc),
                      body.expected_level)


@app.get("/api/assessments/{aid}/profile", response_model=engine.Profile)
def profile(aid: str, _acc: Account = STAFF, s: Session = DB):
    return svc.profile(s, svc.get_or_404(s, Assessment, aid))


@app.post("/api/assessments/{aid}/signoff")
def signoff(aid: str, body: SignoffIn, acc: Account = ASSESSOR, s: Session = DB):
    a = svc.signoff(s, svc.get_or_404(s, Assessment, aid), auth.actor(acc), body.agrees, body.outcome, body.comment)
    return {"id": a.id, "status": a.status, "signoff": json.loads(a.signoff_json)}


# ---- Audit -------------------------------------------------------------------------------------


@app.get("/api/audit")
def audit_log(limit: int = 200, subject: str | None = None, before_seq: int | None = None, _acc: Account = ASSESSOR,
              s: Session = DB):
    """Newest first. Page backwards with before_seq = the smallest seq of the previous page."""
    q = select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(min(limit, 1000))
    if subject:
        q = q.where(AuditEntry.subject == subject)
    if before_seq is not None:
        q = q.where(AuditEntry.seq < before_seq)
    return list(s.exec(q))


@app.get("/api/audit/verify")
def audit_verify(_acc: Account = ASSESSOR, s: Session = DB):
    return audit.verify(s)


# ---- Offline sync ------------------------------------------------------------------------------


@app.post("/api/sync")
def sync(body: SyncIn, acc: Account = STAFF, s: Session = DB):
    """Apply queued offline operations in order. Replaying an op_id returns the stored result. The actor
    of every op is the logged-in account; names in the payload are ignored."""
    results = []
    who = auth.actor(acc)
    for op in body.ops:
        done = s.get(AppliedOp, op.op_id)
        if done:
            results.append({"op_id": op.op_id, "status": "duplicate", "result": json.loads(done.result_json)})
            continue
        p = {**op.payload, "actor": who, "assessor": who}
        try:
            if op.kind in ("pack.confirm", "decision.add") and acc.role not in ("assessor", "admin"):
                raise HTTPException(403, f"{op.kind} needs an assessor account")
            if op.kind == "worker.create":
                r = svc.create_worker(s, p["code"], p.get("preferred_language", "hi"), p.get("actor", "facilitator"),
                                      p.get("id")).model_dump(mode="json")
            elif op.kind == "assessment.create":
                a = svc.create_assessment(s, p["worker_id"], p.get("declaration_text", ""),
                                          p.get("actor", "facilitator"), p.get("id"))
                r = {"id": a.id}
            elif op.kind == "pack.confirm":
                a = svc.confirm_pack(s, svc.get_or_404(s, Assessment, p["assessment_id"]), int(p["nqr_id"]),
                                     p["actor"], p.get("reason"))
                r = {"id": a.id, "confirmed_nqr_id": a.confirmed_nqr_id}
            elif op.kind == "checklist.set":
                r = svc.set_checklist(s, svc.get_or_404(s, Assessment, p["assessment_id"]), p["task_id"], p["ticks"],
                                      p["actor"])
            elif op.kind == "evidence.add":
                ev = svc.add_evidence_b64(s, svc.get_or_404(s, Assessment, p["assessment_id"]), p,
                                          p.get("actor", "facilitator"))
                r = _evidence_out(ev)
            else:  # decision.add
                d = svc.decide(s, svc.get_or_404(s, Assessment, p["assessment_id"]), p["task_id"], p["criterion_id"],
                               p["action"], p.get("level"), p.get("reason"), p["assessor"], p.get("expected_level"))
                r = d.model_dump(mode="json")
        except (HTTPException, KeyError, ValueError, TypeError) as e:
            s.rollback()
            detail = e.detail if isinstance(e, HTTPException) else (
                f"missing field {e}" if isinstance(e, KeyError) else str(e))
            results.append({"op_id": op.op_id, "status": "rejected", "error": detail})
            # Later ops may depend on this one, so stop and let the client surface the problem.
            break
        s.add(AppliedOp(op_id=op.op_id, kind=op.kind, result_json=json.dumps(r, default=str)))
        s.commit()
        results.append({"op_id": op.op_id, "status": "applied", "result": r})
    return {"results": results}


# ---- M4 rater mode -----------------------------------------------------------------------------


@app.get("/api/study/items")
def study_items(rater_id: str, condition: Literal["unassisted", "assisted"], include_sample: bool = False,
                s: Session = DB):
    q = select(StudyItem)
    if not include_sample:
        q = q.where(StudyItem.is_sample == False)  # noqa: E712
    items = list(s.exec(q.order_by(StudyItem.id)))
    # Order is random per rater and condition but reproducible.
    seed = int(hashlib.sha256(f"{rater_id}|{condition}".encode()).hexdigest()[:8], 16)
    random.Random(seed).shuffle(items)
    out = []
    for pos, it in enumerate(items):
        task = engine.get_task(it.task_id)
        cr = next(c for c in task.criteria if c.id == it.criterion_id)
        row = {"position": pos, "item_id": it.id, "image_url": f"/api/study/items/{it.id}/image",
               "is_sample": it.is_sample, "task_title": task.title.model_dump(), "criterion": cr.text.model_dump(),
               "level_names": engine.LEVEL_NAMES}
        if condition == "assisted":
            row["anchors"] = cr.levels
            row["prescore"] = json.loads(it.prescore_json) if it.prescore_json else None
        out.append(row)
    return out


@app.get("/api/study/items/{item_id}/image")
def study_image(item_id: str, s: Session = DB):
    it = svc.get_or_404(s, StudyItem, item_id)
    return FileResponse(DATA / it.image_path)


@app.post("/api/study/ratings")
def add_rating(body: RatingIn, s: Session = DB):
    svc.get_or_404(s, StudyItem, body.item_id)
    if body.client_id and (old := s.exec(select(StudyRating).where(StudyRating.client_id == body.client_id)).first()):
        return old
    r = StudyRating(**body.model_dump())
    s.add(r)
    s.commit()
    s.refresh(r)
    return r


@app.get("/api/study/export", response_class=PlainTextResponse)
def study_export(s: Session = DB):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rater_id", "item_id", "condition", "session", "position", "level", "seconds", "is_sample", "created_at"])
    for r in s.exec(select(StudyRating).order_by(StudyRating.id)):
        it = s.get(StudyItem, r.item_id)
        w.writerow([r.rater_id, r.item_id, r.condition, r.session, r.position, r.level, r.seconds,
                    it.is_sample if it else "", r.created_at.isoformat()])
    return buf.getvalue()

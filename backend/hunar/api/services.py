"""Business logic shared by the REST routes and the offline sync endpoint."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from functools import lru_cache

from fastapi import HTTPException
from sqlmodel import Session, select

from hunar.api.models import Assessment, ChecklistTick, Decision, EvidenceItem, Worker
from hunar.audit import log as audit
from hunar.evidence import detector, hashing, privacy
from hunar.mapper.mapper import QPMapper
from hunar.paths import DATA
from hunar.rubric import engine
from hunar.schemas import MappingResult

UPLOADS = DATA / "uploads"


@lru_cache(maxsize=1)
def mapper() -> QPMapper:
    # MiniLM is the pre-registered primary model (the only one that handles Devanagari);
    # set HUNAR_MAPPER=tfidf for fast tests or HUNAR_MAPPER=hybrid to try the exploratory hybrid.
    return QPMapper(os.environ.get("HUNAR_MAPPER", "minilm"))


def get_or_404(session: Session, model, key):
    obj = session.get(model, key)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {key} not found")
    return obj


def require_open(a: Assessment) -> None:
    if a.status == "signed_off":
        raise HTTPException(409, "assessment is signed off and can no longer change")


# ---- Workers and assessments --------------------------------------------------------------------


def create_worker(s: Session, code: str, preferred_language: str, actor: str, id: str | None = None,
                  is_sample: bool = False) -> Worker:
    if id and (w := s.get(Worker, id)):
        return w
    w = Worker(id=id or str(uuid.uuid4()), code=code, preferred_language=preferred_language, is_sample=is_sample)
    s.add(w)
    audit.append(s, actor, "worker.created", w.id, {"code": code, "is_sample": is_sample}, commit=False)
    s.commit()
    s.refresh(w)
    return w


def create_assessment(s: Session, worker_id: str, declaration_text: str, actor: str, id: str | None = None,
                      is_sample: bool = False) -> Assessment:
    if id and (a := s.get(Assessment, id)):
        return a
    get_or_404(s, Worker, worker_id)
    a = Assessment(id=id or str(uuid.uuid4()), worker_id=worker_id, declaration_text=declaration_text,
                   is_sample=is_sample)
    if declaration_text.strip():
        res = mapper().map(declaration_text)
        a.mapping_json = res.model_dump_json()
    s.add(a)
    audit.append(s, actor, "assessment.created", a.id, {"worker_id": worker_id, "is_sample": is_sample}, commit=False)
    if a.mapping_json:
        top = json.loads(a.mapping_json)["ranking"]
        audit.append(s, "system:mapper", "mapping.suggested", a.id,
                     {"method": mapper().matcher.name, "top": [(r["nqr_id"], r["score"]) for r in top]}, commit=False)
    s.commit()
    s.refresh(a)
    return a


def confirm_pack(s: Session, a: Assessment, nqr_id: int, actor: str, reason: str | None) -> Assessment:
    require_open(a)
    if nqr_id not in {p.nqr_id for p in mapper().packs}:
        raise HTTPException(400, f"unknown qualification pack {nqr_id}")
    suggested = json.loads(a.mapping_json)["ranking"][0]["nqr_id"] if a.mapping_json else None
    if suggested is not None and nqr_id != suggested and not (reason or "").strip():
        raise HTTPException(422, "choosing a pack other than the top suggestion needs a reason")
    a.confirmed_nqr_id = nqr_id
    s.add(a)
    audit.append(s, actor, "pack.confirmed", a.id,
                 {"nqr_id": nqr_id, "suggested": suggested, "agrees_with_suggestion": nqr_id == suggested,
                  "reason": reason}, commit=False)
    s.commit()
    return a


# ---- Practical evidence ---------------------------------------------------------------------------


def set_checklist(s: Session, a: Assessment, task_id: str, ticks: dict[str, bool], actor: str) -> dict[str, bool]:
    require_open(a)
    task = engine.get_task(task_id)
    valid = {c.id for c in task.checklist}
    if bad := set(ticks) - valid:
        raise HTTPException(422, f"unknown checklist items for {task_id}: {sorted(bad)}")
    for item, value in ticks.items():
        row = s.exec(select(ChecklistTick).where(ChecklistTick.assessment_id == a.id,
                                                 ChecklistTick.task_id == task_id,
                                                 ChecklistTick.item_id == item)).first()
        if row:
            row.value, row.actor = value, actor
        else:
            row = ChecklistTick(assessment_id=a.id, task_id=task_id, item_id=item, value=value, actor=actor)
        s.add(row)
    audit.append(s, actor, "checklist.set", a.id, {"task_id": task_id, "ticks": ticks}, commit=False)
    s.commit()
    return checklist_for(s, a.id).get(task_id, {})


def checklist_for(s: Session, assessment_id: str) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {}
    for t in s.exec(select(ChecklistTick).where(ChecklistTick.assessment_id == assessment_id)):
        out.setdefault(t.task_id, {})[t.item_id] = t.value
    return out


def add_evidence(s: Session, a: Assessment, task_id: str, photo_id: str, data: bytes, consent_confirmed: bool,
                 actor: str) -> EvidenceItem:
    require_open(a)
    if not consent_confirmed:
        raise HTTPException(422, "written consent must be confirmed before a photo is stored")
    task = engine.get_task(task_id)
    if photo_id not in {p.id for p in task.photos}:
        raise HTTPException(422, f"unknown photo slot {photo_id} for {task_id}")
    try:
        img = privacy.decode(data)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    blurred, n_faces = privacy.blur_faces(img)  # blur BEFORE anything is written to disk
    jpeg = privacy.encode_jpeg(blurred)
    folder = UPLOADS / a.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{task_id}_{photo_id}_{uuid.uuid4().hex[:8]}.jpg"
    path.write_bytes(jpeg)
    h = hashing.hashes_from_bgr(blurred)
    others = s.exec(select(EvidenceItem.id, EvidenceItem.phash).where(EvidenceItem.assessment_id != a.id)).all()
    dup = hashing.find_duplicate(h.phash, [(i, p) for i, p in others])
    dets = detector.detect(blurred, photo_id)
    ev = EvidenceItem(assessment_id=a.id, task_id=task_id, photo_id=photo_id, stored_path=str(path.relative_to(DATA)),
                      sha256=hashlib.sha256(jpeg).hexdigest(), phash=h.phash, dhash=h.dhash, faces_blurred=n_faces,
                      detector_status="ok" if dets is not None else "unavailable",
                      detections_json=json.dumps(dets) if dets is not None else None,
                      duplicate_of=dup[0] if dup else None, duplicate_distance=dup[1] if dup else None,
                      consent_confirmed=True)
    s.add(ev)
    s.flush()
    audit.append(s, actor, "evidence.added", a.id,
                 {"evidence_id": ev.id, "task_id": task_id, "photo_id": photo_id, "sha256": ev.sha256,
                  "faces_blurred": n_faces, "duplicate_of": ev.duplicate_of, "detector": ev.detector_status},
                 commit=False)
    if dup:
        audit.append(s, "system:hashing", "evidence.possible_reuse", a.id,
                     {"evidence_id": ev.id, "matches": dup[0], "phash_distance": dup[1]}, commit=False)
    s.commit()
    s.refresh(ev)
    return ev


def add_evidence_b64(s: Session, a: Assessment, payload: dict, actor: str) -> EvidenceItem:
    return add_evidence(s, a, payload["task_id"], payload["photo_id"], base64.b64decode(payload["image_b64"]),
                        bool(payload.get("consent_confirmed")), actor)


def evidence_for(s: Session, assessment_id: str) -> list[EvidenceItem]:
    return list(s.exec(select(EvidenceItem).where(EvidenceItem.assessment_id == assessment_id)))


# ---- Pre scores, decisions, profile --------------------------------------------------------------


def _declaration_matches(a: Assessment) -> dict[str, engine.DeclarationMatch]:
    if not a.mapping_json:
        return {}
    res = MappingResult.model_validate_json(a.mapping_json)
    target = a.confirmed_nqr_id or (res.ranking[0].nqr_id if res.ranking else None)
    out = {}
    for pack in res.ranking:
        if pack.nqr_id != target:
            continue
        for m in pack.matched:
            if m.evidence:
                best = m.evidence[0]
                out[m.pc_id] = engine.DeclarationMatch(pc_id=m.pc_id, sentence=best.sentence, similarity=best.similarity)
    return out


def prescores(s: Session, a: Assessment) -> list[engine.PreScore]:
    ticks = checklist_for(s, a.id)
    evidence = evidence_for(s, a.id)
    decl = _declaration_matches(a)
    out = []
    for task in engine.load_tasks():
        task_ev = [e for e in evidence if e.task_id == task.task_id]
        analysed = [e for e in task_ev if e.detections_json is not None]
        dets = None
        if analysed:
            dets = [engine.Detection(**{k: d[k] for k in ("photo_id", "cls", "confidence")})
                    for e in analysed for d in json.loads(e.detections_json)]
        out += engine.prescore_task(task, ticks.get(task.task_id), dets, decl,
                                    declaration_threshold=mapper().matcher.evidence_threshold)
    return out


def latest_decisions(s: Session, assessment_id: str) -> dict[tuple[str, str], Decision]:
    out: dict[tuple[str, str], Decision] = {}
    for d in s.exec(select(Decision).where(Decision.assessment_id == assessment_id).order_by(Decision.id)):
        out[(d.task_id, d.criterion_id)] = d
    return out


def decide(s: Session, a: Assessment, task_id: str, criterion_id: str, action: str, level: int | None,
           reason: str | None, assessor: str) -> Decision:
    require_open(a)
    task = engine.get_task(task_id)
    if criterion_id not in {c.id for c in task.criteria}:
        raise HTTPException(422, f"unknown criterion {criterion_id} in {task_id}")
    pre = next(p for p in prescores(s, a) if p.task_id == task_id and p.criterion_id == criterion_id)
    if action == "accept":
        if pre.suggested_level is None:
            raise HTTPException(422, "there is no suggestion to accept; score this criterion yourself (override)")
        final = pre.suggested_level
    elif action == "override":
        if level not in (0, 1, 2, 3):
            raise HTTPException(422, "override needs a level from 0 to 3")
        if len((reason or "").strip()) < 5:
            raise HTTPException(422, "an override needs a short reason (at least 5 characters)")
        final = level
    else:
        raise HTTPException(422, "action must be accept or override")
    d = Decision(assessment_id=a.id, task_id=task_id, criterion_id=criterion_id, suggested_level=pre.suggested_level,
                 final_level=final, action=action, reason=reason, assessor=assessor)
    s.add(d)
    audit.append(s, assessor, f"criterion.{action}", a.id,
                 {"task_id": task_id, "criterion_id": criterion_id, "suggested": pre.suggested_level,
                  "final": final, "reason": reason}, commit=False)
    s.commit()
    s.refresh(d)
    return d


def profile(s: Session, a: Assessment, task_ids: list[str] | None = None) -> engine.Profile:
    tasks = [t for t in engine.load_tasks() if not task_ids or t.task_id in task_ids]
    dec = latest_decisions(s, a.id)
    levels = {(t.task_id, c.id): (dec[(t.task_id, c.id)].final_level if (t.task_id, c.id) in dec else None)
              for t in tasks for c in t.criteria}
    return engine.aggregate(levels, tasks=tasks)


def signoff(s: Session, a: Assessment, assessor: str, agrees: bool, outcome: str | None, comment: str) -> Assessment:
    require_open(a)
    if a.confirmed_nqr_id is None:
        raise HTTPException(409, "confirm the qualification pack before signing off")
    p = profile(s, a)
    if p.recommendation == "incomplete":
        raise HTTPException(409, f"{len(p.unscored)} criteria still need an assessor decision")
    if not agrees:
        if outcome not in ("not_yet_competent", "recommend_for_certification"):
            raise HTTPException(422, "when disagreeing, state your own outcome")
        if len(comment.strip()) < 5:
            raise HTTPException(422, "when disagreeing, explain why")
    final = p.recommendation if agrees else outcome
    a.status = "signed_off"
    a.signoff_json = json.dumps({"assessor": assessor, "agrees_with_tool": agrees, "tool_recommendation":
                                 p.recommendation, "assessor_outcome": final, "comment": comment,
                                 "overall": p.overall})
    s.add(a)
    audit.append(s, assessor, "assessment.signed_off", a.id, json.loads(a.signoff_json), commit=False)
    s.commit()
    return a

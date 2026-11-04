"""M3 rubric engine: load task rubrics, compute explainable pre scores, aggregate final levels.

Rules (also shown to assessors in the UI):

* A pre score is a *suggestion*. The assessor accepts it or overrides it with a reason.
* Checklist ticks are the assessor's own observations and drive the suggested level:
  none ticked -> 0, some ticked -> 1, all ticked -> 2.
* The engine never suggests level 3 (proficient). Proficiency is an assessor judgement.
* Photo detections (M2) only show that PPE or a tool is *present*. They are reported as reasons;
  they never judge workmanship. With no checklist data, detections alone can suggest at most
  level 2 for presence-type criteria, at low confidence. A disagreement between checklist and
  photos is flagged as a conflict for the assessor to resolve.
* The self-declaration (M1) is reported as context only. Saying you can do something is not
  evidence that you did it, so it never raises a level.
* Aggregation: criterion score = level / 3; NOS and overall scores are weighted means. The pass mark
  comes from the qualification file the tasks belong to (PASS_RULES): 70 % aggregate for all three
  trades, and for the carpenter file also 70 % in each NOS. Any critical (safety) criterion below
  level 2 blocks a positive recommendation.
* Each trade has its own tasks (Task.trade). An assessment uses only the tasks of its trade.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from hunar.paths import RUBRICS

LEVEL_NAMES = {
    0: {"en": "Not performed", "hi": "नहीं किया"},
    1: {"en": "Partial", "hi": "आंशिक"},
    2: {"en": "Competent", "hi": "सक्षम"},
    3: {"en": "Proficient", "hi": "दक्ष"},
}
DEFAULT_PASS_MARK = 0.70
COMPETENT = 2
# "Assessment - Minimum Qualifying Percentage" in Section 2 of each qualification file:
# (aggregate at qualification level, NOS-wise or None when the file leaves it blank).
PASS_RULES: dict[int, tuple[float, float | None]] = {
    13772: (0.70, None),  # Assistant Electrician, QG-03-CO-03951-2025-V2-CSDCI
    12957: (0.70, None),  # Plumber - General, QG-04-PL-03441-2024-V2-WMPS
    9884: (0.70, 0.70),  # Assistant Carpenter, QG-04-WC-00828-2023-V2-FFSC
}


def pass_rules(nqr_id: int) -> tuple[float, float | None]:
    return PASS_RULES.get(nqr_id, (DEFAULT_PASS_MARK, None))


class Text(BaseModel):
    en: str
    hi: str


class ChecklistItem(BaseModel):
    id: str
    en: str
    hi: str


class PhotoSpec(BaseModel):
    id: str
    en: str
    hi: str


class Criterion(BaseModel):
    id: str
    nos: str
    pc_refs: list[str]
    weight: float = 1.0
    critical: bool = False
    text: Text
    checklist: list[str] = Field(default_factory=list)
    cv_classes: list[str] = Field(default_factory=list, description="All must be present")
    cv_classes_any: list[str] = Field(default_factory=list, description="At least one must be present")
    levels: dict[int, str]

    @field_validator("levels")
    @classmethod
    def _four_levels(cls, v: dict[int, str]) -> dict[int, str]:
        if sorted(v) != [0, 1, 2, 3]:
            raise ValueError("each criterion needs anchored descriptors for levels 0, 1, 2 and 3")
        return v

    @field_validator("weight")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("weight must be positive")
        return v


class Task(BaseModel):
    task_id: str
    trade: str = "electrician"
    qualification_nqr_id: int
    review: Text | None = Field(default=None, description="Who wrote the rubric and what review is pending")
    title: Text
    instructions: Text
    photos: list[PhotoSpec]
    checklist: list[ChecklistItem]
    criteria: list[Criterion]

    def model_post_init(self, _ctx) -> None:
        ids = {c.id for c in self.checklist}
        for cr in self.criteria:
            missing = set(cr.checklist) - ids
            if missing:
                raise ValueError(f"{self.task_id}.{cr.id}: unknown checklist items {missing}")


@lru_cache(maxsize=1)
def load_tasks() -> tuple[Task, ...]:
    return tuple(Task.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
                 for p in sorted(RUBRICS.glob("*.yaml")))


def tasks_for(trade: str) -> tuple[Task, ...]:
    return tuple(t for t in load_tasks() if t.trade == trade)


def get_task(task_id: str) -> Task:
    for t in load_tasks():
        if t.task_id == task_id:
            return t
    raise KeyError(task_id)


# ---- Pre scores --------------------------------------------------------------------------------


class Detection(BaseModel):
    photo_id: str
    cls: str
    confidence: float


class DeclarationMatch(BaseModel):
    pc_id: str
    sentence: str
    similarity: float


class PreScore(BaseModel):
    task_id: str
    criterion_id: str
    suggested_level: int | None
    confidence: Literal["none", "low", "medium", "high"]
    reasons: list[str]
    conflict: bool = False


def _cv_status(cr: Criterion, detections: list[Detection] | None, min_conf: float) -> tuple[bool | None, list[str]]:
    """(present?, reasons). None when the criterion has no visual signal or no photos were analysed."""
    if not (cr.cv_classes or cr.cv_classes_any) or detections is None:
        return None, []
    best: dict[str, Detection] = {}
    for d in detections:
        if d.confidence >= min_conf and (d.cls not in best or d.confidence > best[d.cls].confidence):
            best[d.cls] = d
    reasons = [f"{d.cls.replace('_', ' ')} detected in photo {d.photo_id}, confidence {d.confidence:.2f}"
               for c in cr.cv_classes + cr.cv_classes_any if (d := best.get(c))]
    missing = [c for c in cr.cv_classes if c not in best]
    reasons += [f"{c.replace('_', ' ')} not detected in any photo" for c in missing]
    any_ok = not cr.cv_classes_any or any(c in best for c in cr.cv_classes_any)
    if cr.cv_classes_any and not any_ok:
        reasons.append("none of " + ", ".join(c.replace("_", " ") for c in cr.cv_classes_any) + " detected")
    return (not missing and any_ok), reasons


def prescore_criterion(task: Task, cr: Criterion, checklist: dict[str, bool] | None,
                       detections: list[Detection] | None, declaration: list[DeclarationMatch] | None,
                       min_conf: float = 0.5) -> PreScore:
    reasons: list[str] = []
    level: int | None = None
    has_checklist = checklist is not None and bool(cr.checklist) and any(i in checklist for i in cr.checklist)
    if has_checklist:
        ticked = [i for i in cr.checklist if checklist.get(i)]
        level = 0 if not ticked else (COMPETENT if len(ticked) == len(cr.checklist) else 1)
        names = {c.id: c.en for c in task.checklist}
        reasons.append(f"checklist: {len(ticked)} of {len(cr.checklist)} observed items ticked")
        reasons += [f"not ticked: {names[i]}" for i in cr.checklist if i not in ticked]

    cv_present, cv_reasons = _cv_status(cr, detections, min_conf)
    reasons += cv_reasons
    conflict = False
    if cv_present is not None:
        if level is None:
            level = COMPETENT if cv_present else None
            if cv_present:
                reasons.append("suggested from photos only: presence detected, workmanship not judged")
        elif cv_present is False and level >= COMPETENT:
            conflict = True
            reasons.append("conflict: checklist says done but photos do not show it; assessor to check")

    for m in sorted(declaration or [], key=lambda m: -m.similarity)[:1]:
        reasons.append(f'worker\'s declaration mentions this: "{m.sentence}" (similarity {m.similarity:.2f}); '
                       "context only, not scored")

    if level is None:
        reasons.append("not enough observed evidence; assessor must score this criterion")
        confidence = "none"
    elif conflict or not has_checklist:
        confidence = "low"
    elif cv_present is True and level >= COMPETENT:
        confidence = "high"
    else:
        confidence = "medium"
    return PreScore(task_id=task.task_id, criterion_id=cr.id, suggested_level=level, confidence=confidence,
                    reasons=reasons, conflict=conflict)


def prescore_task(task: Task, checklist: dict[str, bool] | None = None, detections: list[Detection] | None = None,
                  declaration_pc_scores: dict[str, DeclarationMatch] | None = None,
                  declaration_threshold: float = 0.5) -> list[PreScore]:
    out = []
    for cr in task.criteria:
        decl = [m for pc in cr.pc_refs if (m := (declaration_pc_scores or {}).get(pc))
                and m.similarity >= declaration_threshold]
        out.append(prescore_criterion(task, cr, checklist, detections, decl))
    return out


# ---- Aggregation -------------------------------------------------------------------------------


class NOSResult(BaseModel):
    nos: str
    score: float
    criteria: int
    below_competent: int


class Gap(BaseModel):
    task_id: str
    criterion_id: str
    nos: str
    level: int
    critical: bool
    text: str


class Profile(BaseModel):
    overall: float | None
    pass_mark: float
    nos_pass_mark: float | None = None
    nos: list[NOSResult]
    gaps: list[Gap]
    critical_failures: list[Gap]
    unscored: list[str]
    recommendation: Literal["incomplete", "not_yet_competent", "recommend_for_certification"]
    explanation: str
    requires_assessor_signoff: bool = True


def aggregate(final_levels: dict[tuple[str, str], int | None], tasks: list[Task] | None = None,
              pass_mark: float = DEFAULT_PASS_MARK, nos_pass_mark: float | None = None) -> Profile:
    """Aggregate final (assessor-confirmed) levels into an NSQF competency profile.

    `final_levels` maps (task_id, criterion_id) to 0..3, or None when not scored yet.
    Only tasks that appear in `final_levels` are included unless `tasks` is given.
    `nos_pass_mark`, when the qualification file sets one, must be met by every NOS the tasks cover.
    """
    if not 0.0 < pass_mark <= 1.0:
        raise ValueError("pass_mark must be in (0, 1]")
    if nos_pass_mark is not None and not 0.0 < nos_pass_mark <= 1.0:
        raise ValueError("nos_pass_mark must be in (0, 1]")
    if tasks is None:
        used = {t for t, _ in final_levels}
        tasks = [t for t in load_tasks() if t.task_id in used]
    if not tasks:
        raise ValueError("no tasks to aggregate")
    num, den = 0.0, 0.0
    nos_num: dict[str, float] = defaultdict(float)
    nos_den: dict[str, float] = defaultdict(float)
    nos_n: dict[str, int] = defaultdict(int)
    nos_low: dict[str, int] = defaultdict(int)
    gaps, critical, unscored = [], [], []
    for t in tasks:
        for cr in t.criteria:
            lvl = final_levels.get((t.task_id, cr.id))
            if lvl is None:
                unscored.append(f"{t.task_id}.{cr.id}")
                continue
            if lvl not in (0, 1, 2, 3):
                raise ValueError(f"level for {t.task_id}.{cr.id} must be 0..3, got {lvl}")
            s = lvl / 3
            num += cr.weight * s
            den += cr.weight
            nos_num[cr.nos] += cr.weight * s
            nos_den[cr.nos] += cr.weight
            nos_n[cr.nos] += 1
            if lvl < COMPETENT:
                nos_low[cr.nos] += 1
                g = Gap(task_id=t.task_id, criterion_id=cr.id, nos=cr.nos, level=lvl, critical=cr.critical,
                        text=cr.text.en)
                gaps.append(g)
                if cr.critical:
                    critical.append(g)
    overall = round(num / den, 4) if den else None
    nos = [NOSResult(nos=k, score=round(nos_num[k] / nos_den[k], 4), criteria=nos_n[k], below_competent=nos_low[k])
           for k in sorted(nos_den)]
    if unscored:
        rec, why = "incomplete", f"{len(unscored)} criteria are not scored yet."
    elif critical:
        rec = "not_yet_competent"
        why = ("A critical safety criterion is below 'competent': "
               + "; ".join(f"{g.task_id}.{g.criterion_id}" for g in critical)
               + ". A positive recommendation is blocked whatever the overall score.")
    elif overall is None or overall + 1e-9 < pass_mark:
        rec = "not_yet_competent"
        why = f"Overall {overall:.0%} is below the pass mark of {pass_mark:.0%}."
    elif nos_pass_mark is not None and (low := [n for n in nos if n.score + 1e-9 < nos_pass_mark]):
        rec = "not_yet_competent"
        why = (f"Overall {overall:.0%} meets the pass mark, but the qualification file also needs "
               f"{nos_pass_mark:.0%} in each NOS: " + "; ".join(f"{n.nos} {n.score:.0%}" for n in low) + ".")
    else:
        rec = "recommend_for_certification"
        why = f"Overall {overall:.0%} meets the pass mark of {pass_mark:.0%}"
        why += f" and every NOS meets {nos_pass_mark:.0%}" if nos_pass_mark is not None else ""
        why += ", and all critical criteria are competent."
    return Profile(overall=overall, pass_mark=pass_mark, nos_pass_mark=nos_pass_mark, nos=nos, gaps=gaps,
                   critical_failures=critical,
                   unscored=unscored, recommendation=rec,
                   explanation=why + " This is a recommendation for the assessor, not a certificate.")

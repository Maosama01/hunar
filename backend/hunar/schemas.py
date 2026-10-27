"""Pydantic schemas shared by the mapper, rubric engine and API.

A qualification pack (QP / qualification file) is stored as structured JSON in
data/processed/qp/<nqr_id>.json and validated against `QualificationPack`.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ParseMethod = Literal["pdf_auto", "pdf_auto_hand_checked", "stub"]


class Source(BaseModel):
    pdf_url: str | None = None
    page_url: str | None = None
    downloaded_on: str | None = None
    sha256: str | None = None


class PerformanceCriterion(BaseModel):
    id: str = Field(description="Globally unique id: <nos_code>.<pc_code>")
    code: str = Field(description="PC number as printed, e.g. PC3")
    text: str


class NOS(BaseModel):
    code: str | None = Field(default=None, description="NOS code, e.g. CON/N0604")
    title: str
    core: bool | None = None
    nsqf_level: float | None = None
    hours: float | None = None
    performance_criteria: list[PerformanceCriterion] = Field(default_factory=list)
    knowledge_items: list[str] = Field(
        default_factory=list,
        description="Knowledge and understanding items. The NCVET qualification file does not list "
        "them; they live in the separate NOS documents and are not parsed yet.",
    )


class QualificationPack(BaseModel):
    nqr_id: int
    nqr_code: str | None = None
    title: str
    sector: str | None = None
    nsqf_level: float | None = None
    awarding_body: str | None = None
    role: Literal["target", "distractor"] = "distractor"
    is_stub: bool = False
    parse_method: ParseMethod
    verification_note: str = ""
    source: Source = Field(default_factory=Source)
    nos: list[NOS]

    def criteria(self) -> list[tuple[NOS, PerformanceCriterion]]:
        return [(n, pc) for n in self.nos for pc in n.performance_criteria]

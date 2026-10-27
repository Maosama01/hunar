"""M1 qualification pack mapper: declaration text -> ranked packs with explanations.

Aggregation (fixed before any evaluation was run, identical for every matcher):

1. Split the declaration into short units (sentences / clauses).
2. Similarity matrix S between units and every performance criterion (PC) of every pack.
3. Pack score = mean over units of the best similarity to any *core* PC of that pack.
   A declaration is partial, so we ask "how well does this pack explain what the worker said",
   not "how much of the pack did they mention".
4. For explanation: PC score = best similarity of any unit to the PC; NOS score = mean of the
   top-3 PC scores; a PC is "matched" when its score reaches the matcher's evidence threshold,
   and core PCs below it are reported as skill gaps.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from hunar.mapper import matchers
from hunar.mapper.text import split_sentences
from hunar.paths import DATA
from hunar.schemas import CriterionMatch, Evidence, MappingResult, NOSCoverage, PackScore, QualificationPack


def load_packs(qp_dir: Path | None = None) -> list[QualificationPack]:
    qp_dir = qp_dir or DATA / "processed" / "qp"
    order = [p["nqr_id"] for p in json.loads((DATA / "qp_sources.json").read_text())["packs"]]
    packs = {int(f.stem): QualificationPack.model_validate_json(f.read_text()) for f in qp_dir.glob("*.json")}
    return [packs[i] for i in order if i in packs]


class QPMapper:
    def __init__(self, matcher: matchers.Matcher | str = "minilm", packs: list[QualificationPack] | None = None,
                 top_k_nos: int = 3, max_evidence: int = 2):
        self.matcher = matchers.build(matcher) if isinstance(matcher, str) else matcher
        self.packs = packs if packs is not None else load_packs()
        self.top_k_nos = top_k_nos
        self.max_evidence = max_evidence
        self._rows = []  # (pack index, nos, pc)
        for pi, qp in enumerate(self.packs):
            for nos, pc in qp.criteria():
                self._rows.append((pi, nos, pc))
        self._pack_idx = np.array([r[0] for r in self._rows])
        self._core = np.array([r[1].core is not False for r in self._rows])
        self.matcher.fit([r[2].text for r in self._rows])

    def pack_scores(self, sentences: list[str]) -> tuple[np.ndarray, np.ndarray]:
        sims = self.matcher.similarity(sentences)
        scores = np.zeros(len(self.packs))
        for pi in range(len(self.packs)):
            cols = (self._pack_idx == pi) & self._core
            if not cols.any():
                cols = self._pack_idx == pi
            scores[pi] = sims[:, cols].max(axis=1).mean()
        return scores, sims

    def rank(self, text: str) -> list[int]:
        """nqr_ids ordered best first (used by the evaluation)."""
        scores, _ = self.pack_scores(split_sentences(text))
        return [self.packs[i].nqr_id for i in np.argsort(-scores, kind="stable")]

    def map(self, text: str, top_n: int = 3) -> MappingResult:
        sentences = split_sentences(text)
        scores, sims = self.pack_scores(sentences)
        thr = self.matcher.evidence_threshold
        ranking = []
        for rank, pi in enumerate(np.argsort(-scores, kind="stable")[:top_n], start=1):
            qp = self.packs[pi]
            cols = np.where(self._pack_idx == pi)[0]
            matched, gaps, nos_rows = [], [], {}
            for j in cols:
                _, nos, pc = self._rows[j]
                col = sims[:, j]
                best = float(col.max())
                ev = [Evidence(sentence=sentences[i], similarity=round(float(col[i]), 3))
                      for i in np.argsort(-col)[: self.max_evidence] if col[i] >= thr]
                cm = CriterionMatch(pc_id=pc.id, nos_code=nos.code, text=pc.text, score=round(best, 3), evidence=ev)
                (matched if ev else gaps if nos.core is not False else []).append(cm)
                nos_rows.setdefault(nos.code, (nos, []))[1].append(best)
            nos_cov = []
            for nos, vals in nos_rows.values():
                top = sorted(vals, reverse=True)[: self.top_k_nos]
                nos_cov.append(NOSCoverage(code=nos.code, title=nos.title, core=nos.core,
                                           score=round(float(np.mean(top)), 3),
                                           matched=sum(v >= thr for v in vals), total=len(vals)))
            matched.sort(key=lambda m: -m.score)
            ranking.append(PackScore(nqr_id=qp.nqr_id, title=qp.title, nsqf_level=qp.nsqf_level, rank=rank,
                                     score=round(float(scores[pi]), 3), nos=nos_cov, matched=matched, gaps=gaps))
        return MappingResult(method=self.matcher.name, sentences=sentences, ranking=ranking)

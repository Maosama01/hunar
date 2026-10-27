import json

import pytest

from hunar.paths import DATA
from hunar.schemas import QualificationPack

QP_DIR = DATA / "processed" / "qp"
SOURCES = json.loads((DATA / "qp_sources.json").read_text())["packs"]


def test_stub_fixture_is_marked_and_valid(stub_qp):
    assert stub_qp.is_stub and "STUB, NOT OFFICIAL" in stub_qp.title


@pytest.mark.parametrize("meta", SOURCES, ids=[str(m["nqr_id"]) for m in SOURCES])
def test_processed_pack_matches_source(meta):
    qp = QualificationPack.model_validate_json((QP_DIR / f"{meta['nqr_id']}.json").read_text())
    assert not qp.is_stub
    assert qp.source.sha256 and qp.source.pdf_url == meta["pdf_url"]
    assert qp.nos, "every pack has at least one NOS"
    for nos in qp.nos:
        assert nos.performance_criteria, f"{nos.code} has no performance criteria"
        assert all(pc.text.strip() for pc in nos.performance_criteria)
    ids = [pc.id for _, pc in qp.criteria()]
    assert len(ids) == len(set(ids)), "PC ids are unique within a pack"


def test_target_pack_nos_codes():
    qp = QualificationPack.model_validate_json((QP_DIR / "13772.json").read_text())
    codes = [n.code for n in qp.nos]
    # Codes printed in the official module summary (QF QG-03-CO-03951-2025-V2-CSDCI).
    for code in ["CON/N0602", "CON/N0603", "CON/N0604", "CON/N0605", "CON/N9001"]:
        assert code in codes

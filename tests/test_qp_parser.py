import json

import pytest

from hunar.paths import DATA
from hunar.schemas import QualificationPack

QP_DIR = DATA / "processed" / "qp"
SOURCES = json.loads((DATA / "qp_sources.json").read_text())["packs"]
ALL_SOURCES = SOURCES + json.loads((DATA / "qp_sources.json").read_text()).get("trade_packs", [])


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


@pytest.mark.parametrize("meta", ALL_SOURCES, ids=[str(m["nqr_id"]) for m in ALL_SOURCES])
def test_every_nos_has_its_code_and_unbroken_criteria(meta):
    """Regression for layouts the parser once got wrong: names and codes wrapped onto extra rows,
    tables continued on a new page, rows printed above a page's table, two criteria in one cell and
    outcome headings glued onto a criterion."""
    import re

    qp = QualificationPack.model_validate_json((QP_DIR / f"{meta['nqr_id']}.json").read_text())
    for nos in qp.nos:
        assert "/" in nos.code and not nos.code.startswith(f"{meta['nqr_id']}/"), f"{nos.code}: code not found"
        assert len(nos.title.split()) >= 2 and "PC" not in nos.title, f"{nos.code}: title {nos.title[:40]!r}"
        numbers = [int(pc.code[2:]) for pc in nos.performance_criteria]
        assert numbers == list(range(1, len(numbers) + 1)), f"{nos.code}: PCs {numbers}"
        for pc in nos.performance_criteria:
            assert not re.search(r"\sPC\s*\d+\s*[.:)]\s", pc.text), f"{pc.id} holds a second criterion"


def test_known_fixes_in_the_trade_packs():
    plumber = QualificationPack.model_validate_json((QP_DIR / "12957.json").read_text())
    n0142 = next(n for n in plumber.nos if n.code == "PSC/N0142")
    assert len(n0142.performance_criteria) == 24  # PC1-PC24 in the official file; once parsed as 1
    n0133 = next(n for n in plumber.nos if n.code == "PSC/N0133")
    assert not n0133.performance_criteria[3].text.endswith("related accessories")  # a heading, not PC4
    carpenter = QualificationPack.model_validate_json((QP_DIR / "9884.json").read_text())
    titles = {n.code: n.title for n in carpenter.nos}
    assert titles["FFS/N2206"] == "Prepare the worksite for on-site operations"
    assert "DGT/VSQ/N0102" in titles

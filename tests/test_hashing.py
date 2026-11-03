import random

import imagehash
import pytest
from sqlmodel import Session, SQLModel, create_engine, select, text

from hunar.api import services
from hunar.api.models import Assessment, EvidenceItem, PhashBand, Worker
from hunar.evidence import hashing


def rand_hash(rng: random.Random) -> str:
    return f"{rng.getrandbits(64):016x}"


def flip(h: str, n: int, rng: random.Random) -> str:
    v = int(h, 16)
    for b in rng.sample(range(64), n):
        v ^= 1 << b
    return f"{v:016x}"


def test_distance_matches_imagehash():
    rng = random.Random(1)
    for _ in range(500):
        a, b = rand_hash(rng), rand_hash(rng)
        assert hashing.distance(a, b) == imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)
    assert hashing.distance("0" * 16, "f" * 16) == 64
    with pytest.raises(ValueError):
        hashing.distance("00", "0000")


def test_bands_cover_every_bit_once():
    assert hashing.BANDS == hashing.DEFAULT_PHASH_THRESHOLD + 1
    bands = hashing.phash_bands("f" * 16)
    assert len(bands) == hashing.BANDS
    assert sum(v.bit_count() for v in bands) == 64  # widths 13, 13, 13, 13, 12
    assert hashing.phash_bands("0" * 16) == [0] * hashing.BANDS


@pytest.mark.parametrize("bits", range(hashing.DEFAULT_PHASH_THRESHOLD + 1))
def test_pairs_within_threshold_share_a_band(bits):
    rng = random.Random(bits)
    for _ in range(300):
        a = rand_hash(rng)
        b = flip(a, bits, rng)
        assert any(x == y for x, y in zip(hashing.phash_bands(a), hashing.phash_bands(b), strict=True))


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Worker(id="w", code="W001"))
        for aid in ("a1", "a2", "a3"):
            s.add(Assessment(id=aid, worker_id="w"))
        s.commit()
        yield s


def store(s: Session, assessment_id: str, phash: str, indexed: bool = True) -> int:
    ev = EvidenceItem(assessment_id=assessment_id, task_id="t", photo_id="p", stored_path="x", sha256="",
                      phash=phash, dhash=phash)
    s.add(ev)
    s.flush()
    if indexed:
        s.add_all(services._band_rows(ev.id, phash))
    s.commit()
    return ev.id


def brute_force(s: Session, assessment_id: str, phash: str):
    rows = s.exec(select(EvidenceItem.id, EvidenceItem.phash).where(EvidenceItem.assessment_id != assessment_id)
                  .order_by(EvidenceItem.id)).all()
    return hashing.find_duplicate(phash, [(i, p) for i, p in rows])


def test_find_reuse_equals_full_scan(session):
    rng = random.Random(7)
    stored = []
    for _ in range(300):
        h = flip(rng.choice(stored), rng.randint(0, 8), rng) if stored and rng.random() < 0.5 else rand_hash(rng)
        stored.append(h)
        store(session, rng.choice(["a1", "a2"]), h)
    for _ in range(300):
        q = flip(rng.choice(stored), rng.randint(0, 6), rng) if rng.random() < 0.7 else rand_hash(rng)
        aid = rng.choice(["a1", "a2", "a3"])
        assert services.find_reuse(session, aid, q) == brute_force(session, aid, q)


def test_find_reuse_ties_and_own_assessment(session):
    base = "0" * 16
    first = store(session, "a1", flip(base, 2, random.Random(1)))
    store(session, "a1", flip(base, 2, random.Random(2)))  # same distance, stored later
    store(session, "a2", base)  # exact match, but in the asking assessment
    assert services.find_reuse(session, "a2", base) == (first, 2)
    assert services.find_reuse(session, "a1", base)[1] == 0
    assert services.find_reuse(session, "a3", "f" * 16) is None


def test_reuse_query_uses_the_band_index(session):
    store(session, "a1", "0123456789abcdef")
    sql = str(services.reuse_candidates("a2", "0123456789abcdef").compile(
        dialect=session.get_bind().dialect, compile_kwargs={"literal_binds": True}))
    plan = " ".join(str(r) for r in session.exec(text(f"EXPLAIN QUERY PLAN {sql}")).all())
    assert "ix_phashband_band_value" in plan
    assert "SCAN evidenceitem" not in plan  # candidates are looked up by id, not found by reading every photo


def test_index_phashes_backfills_old_and_stale_rows(session):
    old = store(session, "a1", "0123456789abcdef", indexed=False)
    stale = store(session, "a1", "fedcba9876543210")
    session.delete(session.exec(select(PhashBand).where(PhashBand.evidence_id == stale, PhashBand.band == 0)).one())
    session.commit()
    assert services.find_reuse(session, "a2", "0123456789abcdef") is None  # not indexed yet
    assert services.index_phashes(session) == 2
    assert services.find_reuse(session, "a2", "0123456789abcdef") == (old, 0)
    assert services.find_reuse(session, "a2", "fedcba9876543210") == (stale, 0)
    assert services.index_phashes(session) == 0


def test_index_phashes_rebuilds_after_a_layout_change(session):
    ids = [store(session, "a1", h) for h in ("0123456789abcdef", "fedcba9876543210")]
    for band in session.exec(select(PhashBand)).all():  # as if indexed under an older layout
        band.value += 1
    session.commit()
    assert services.find_reuse(session, "a2", "0123456789abcdef") is None
    assert services.index_phashes(session) == 2
    assert services.find_reuse(session, "a2", "0123456789abcdef") == (ids[0], 0)
    assert services.index_phashes(session) == 0

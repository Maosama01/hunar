"""Guided clips (video pilot). All clips and transcripts here are SYNTHETIC: generated frames with no
person and a made-up transcript. They check the pipeline, not how well it works on real workers."""
from fractions import Fraction

import av
import numpy as np
import pytest
from sqlmodel import Session, select

from hunar.api import db
from hunar.api.models import AuditEntry, GuidedClip
from hunar.rubric.engine import ClipEvidence, get_task, prescore_criterion
from hunar.video import detect
from hunar.video.clips import match_terms, meter_in_range


@pytest.fixture(autouse=True)
def no_real_detector(monkeypatch):
    """These tests never load model weights, even when `make clip-models` has been run here."""
    monkeypatch.setenv("HUNAR_CLIP_DETECTOR", "none")
    detect.detector.cache_clear()
    yield
    getattr(detect.detector, "cache_clear", lambda: None)()  # a test may have swapped in a stand-in

FAN_PARTS = get_task("fan2_parts")


def _crit(task, cid):
    return next(c for c in task.criteria if c.id == cid)


def _words(text, step=0.5):
    return [{"word": w, "start": i * step} for i, w in enumerate(text.split())]


# ---- term matching and meter --------------------------------------------------------------------


def test_terms_match_english_hindi_hinglish_and_phrases():
    terms = {"name": ["capacitor", "कैपेसिटर"], "failure": ["dheema", "full speed"], "test": ["meter"]}
    found = match_terms(_words("yeh capacitors hai, isse fan dheema chalta hai"), terms)
    assert found["name"] == [("capacitor", 0.5)] and found["failure"][0][0] == "dheema" and "test" not in found
    assert match_terms(_words("यह कैपेसिटर है।"), terms)["name"] == [("कैपेसिटर", 0.5)]
    assert match_terms(_words("runs at full speed only"), terms)["failure"] == [("full speed", 1.0)]
    assert "test" not in match_terms(_words("metro station"), {"test": ["meter"]})  # not a prefix of the word


@pytest.mark.parametrize("reading, printed, tol, ok", [(2.4, 2.5, 5, True), (2.0, 2.5, 5, False), (2.3, 2.5, None, True),
                                                       (2.2, 2.5, None, False), (None, 2.5, 5, None), (2.4, None, 5, None)])
def test_meter_reading_against_printed_value(reading, printed, tol, ok):
    assert meter_in_range(reading, printed, tol) is ok


# ---- suggested levels from a clip ---------------------------------------------------------------


def _pre(cid, **ev):
    cr = _crit(FAN_PARTS, cid)
    return prescore_criterion(FAN_PARTS, cr, None, None, None, clips={cr.clip.id: ClipEvidence(clip_id=cr.clip.id, **ev)})


def test_explained_and_handled_suggests_competent_never_proficient():
    p = _pre("c2_cap_explain", found={"name": [("capacitor", 3.0)], "function": [("start", 5.0)]}, part_seen=True,
             hand_on_part=True)
    assert p.suggested_level == 2 and p.confidence == "low"
    assert any('"capacitor" at 0:03' in r for r in p.reasons)


def test_explained_but_frames_not_checked_suggests_partial():
    p = _pre("c2_cap_explain", found={"name": [("capacitor", 3.0)], "function": [("start", 5.0)]})
    assert p.suggested_level == 1 and any("frames not checked" in r for r in p.reasons)


def test_hand_not_checked_falls_back_to_the_part_being_shown():
    found = {"name": [("capacitor", 3.0)], "function": [("start", 5.0)]}
    p = _pre("c2_cap_explain", found=found, part_seen=True, hand_on_part=None)
    assert p.suggested_level == 2 and p.confidence == "low"
    assert any("part shown" in r and "hand not checked" in r for r in p.reasons)
    assert _pre("c2_cap_explain", found=found, part_seen=False, hand_on_part=None).suggested_level == 1


def test_handled_but_silent_is_partial_and_neither_is_zero():
    assert _pre("c5_bearings", part_seen=True, hand_on_part=True).suggested_level == 1
    assert _pre("c5_bearings", part_seen=False, hand_on_part=False).suggested_level == 0


def test_meter_outside_printed_value_caps_the_suggestion():
    full = {"failure": [("dheema", 2.0)], "test": [("meter", 4.0)]}
    p = _pre("c3_cap_diagnose", found=full, part_seen=True, hand_on_part=True, meter_value=1.6, meter_in_range=False)
    assert p.suggested_level == 1 and any("outside the value printed" in r for r in p.reasons)
    ok = _pre("c3_cap_diagnose", found=full, part_seen=True, hand_on_part=True, meter_value=2.45, meter_in_range=True)
    assert ok.suggested_level == 2


def test_checklist_leads_and_an_empty_clip_is_a_conflict():
    task = get_task("fan4_reassemble_run")
    cr = _crit(task, "c2_run")
    ticks = {"runs_all_speeds": True, "no_wobble_noise": True}
    p = prescore_criterion(task, cr, ticks, None, None,
                           clips={"run_test": ClipEvidence(clip_id="run_test", part_seen=False, hand_on_part=False)})
    assert p.suggested_level == 2 and p.conflict and p.confidence == "low"


# ---- the whole pipeline through the API (synthetic clip) ----------------------------------------


def synthetic_clip(seconds=2, with_audio=True) -> bytes:
    """SYNTHETIC: a moving grey square (no person) with a tone; stands in for a phone recording."""
    import io

    buf = io.BytesIO()
    with av.open(buf, "w", format="webm") as c:
        v = c.add_stream("libvpx", rate=30)
        v.width, v.height, v.pix_fmt = 960, 540, "yuv420p"
        a = c.add_stream("libopus", rate=48000) if with_audio else None
        if a:
            a.layout = "mono"
        for i in range(30 * seconds):
            img = np.full((540, 960, 3), 30, np.uint8)
            img[100:300, 50 + i * 5:250 + i * 5] = 200
            f = av.VideoFrame.from_ndarray(img, format="bgr24")
            f.pts, f.time_base = i, Fraction(1, 30)
            for p in v.encode(f):
                c.mux(p)
        for p in v.encode():
            c.mux(p)
        if a:
            tone = (0.2 * np.sin(2 * np.pi * 440 * np.arange(48000 * seconds) / 48000)).astype(np.float32).reshape(1, -1)
            for k in range(0, tone.shape[1], 960):
                fr = av.AudioFrame.from_ndarray(tone[:, k:k + 960], format="flt", layout="mono")
                fr.sample_rate, fr.pts = 48000, k
                for p in a.encode(fr):
                    c.mux(p)
            for p in a.encode():
                c.mux(p)
    return buf.getvalue()


@pytest.fixture
def fake_speech(monkeypatch):
    """A made-up transcript instead of Whisper (the real model is slow and needs real speech)."""
    from hunar.speech import transcribe as tr

    said = "yeh capacitor hai fan ko start karne mein madad karta hai"
    monkeypatch.setattr(tr, "available", lambda: True)
    monkeypatch.setattr(tr, "transcribe_words", lambda path, language=None: {"text": said, "words": _words(said),
                                                                             "language": "hi", "model": "fake"})


def _fan_assessment(client):
    w = client.post("/api/workers", json={"code": "SYN-FAN", "preferred_language": "hi"}).json()
    a = client.post("/api/assessments", json={"worker_id": w["id"], "trade": "appliance_technician",
                                              "declaration_text": "", "actor": "A"}).json()
    assert a["trade"] == "appliance_technician"
    return a["id"]


def _upload(client, aid, task_id="fan2_parts", clip_id="capacitor", consent=True, **form):
    data = {"task_id": task_id, "clip_id": clip_id, "consent_confirmed": str(consent).lower(), "language": "hi",
            **{k: str(v) for k, v in form.items()}}
    return client.post(f"/api/assessments/{aid}/clips", data=data,
                       files={"file": ("clip.webm", synthetic_clip(), "video/webm")})


def test_clip_is_stored_blurred_and_silent_and_feeds_the_suggestion(client, fake_speech):
    aid = _fan_assessment(client)
    r = _upload(client, aid, reading=2.4, printed=2.5, tolerance_pct=5)
    assert r.status_code == 200, r.text
    clip = r.json()
    assert clip["found"]["name"][0][0] == "capacitor" and clip["found"]["function"][0][0] == "start"
    assert clip["meter_in_range"] is True and clip["detector"] == "none" and clip["part_seen"] is None
    video = client.get(clip["video_url"])
    assert video.status_code == 200 and video.headers["content-type"] == "video/mp4"
    import io

    with av.open(io.BytesIO(video.content)) as stored:
        assert [s.type for s in stored.streams] == ["video"]  # the sound was removed
        assert stored.streams.video[0].codec_context.name == "h264" and stored.streams.video[0].width == 640
    pre = {p["criterion_id"]: p for p in client.get(f"/api/assessments/{aid}/prescores").json()
           if p["task_id"] == "fan2_parts"}
    assert pre["c2_cap_explain"]["suggested_level"] == 1  # explained, but the frames were not checked
    assert pre["c3_cap_diagnose"]["suggested_level"] == 0  # failure and test were not mentioned
    assert pre["c4_winding"]["suggested_level"] is None  # no clip yet
    detail = client.get(f"/api/assessments/{aid}").json()
    assert detail["clips"][0]["clip_id"] == "capacitor" and "stored_path" not in detail["clips"][0]
    with Session(db.engine()) as s:
        row = s.exec(select(GuidedClip)).one()
        assert row.consent_confirmed and row.frames_with_faces == 0
        assert s.exec(select(AuditEntry).where(AuditEntry.action == "clip.added")).first() is not None


def test_clip_needs_consent_a_known_prompt_and_the_right_trade(client, fake_speech):
    aid = _fan_assessment(client)
    assert _upload(client, aid, consent=False).status_code == 422
    assert _upload(client, aid, clip_id="tyres").status_code == 422
    w = client.post("/api/workers", json={"code": "SYN-EL", "preferred_language": "hi"}).json()
    el = client.post("/api/assessments", json={"worker_id": w["id"], "declaration_text": "", "actor": "A"}).json()
    assert _upload(client, el["id"]).status_code == 422  # a fan task on an electrician assessment
    bad = client.post(f"/api/assessments/{aid}/clips", data={"task_id": "fan2_parts", "clip_id": "capacitor",
                                                             "consent_confirmed": "true"},
                      files={"file": ("clip.webm", b"not a video", "video/webm")})
    assert bad.status_code == 422
    with Session(db.engine()) as s:
        assert s.exec(select(GuidedClip)).all() == []


def test_fan_assessment_confirms_only_the_appliance_file(client):
    aid = _fan_assessment(client)
    assert client.post(f"/api/assessments/{aid}/confirm-pack", json={"nqr_id": 13772, "actor": "A"}).status_code == 400
    assert client.post(f"/api/assessments/{aid}/confirm-pack", json={"nqr_id": 14861, "actor": "A"}).status_code == 200
    packs = {p["nqr_id"]: p["trade"] for p in client.get("/api/packs").json()}
    assert packs[14861] == "appliance_technician"


# ---- frame check (stand-in model; the real one needs `make clip-models`) ------------------------


def test_boxes_overlap_only_when_they_share_area():
    assert detect.overlaps((0, 0, 10, 10), (5, 5, 15, 15))
    assert not detect.overlaps((0, 0, 10, 10), (10, 0, 20, 10))  # touching edges only
    assert not detect.overlaps((0, 0, 10, 10), (20, 20, 30, 30))


def test_summary_needs_the_hand_and_the_part_in_the_same_frame():
    part = [("capacitor", 0.6, (100, 100, 200, 200))]
    frames = [{"t": 0.0, "part": part, "hands": [(0.9, (400, 400, 450, 450))]},  # part seen, hand elsewhere
              {"t": 1.0, "part": [], "hands": [(0.9, (110, 110, 150, 150))]}]  # hand where the part was, part gone
    s = detect.summarise(frames, 0.25, 0.25)
    assert s["part_seen"] is True and s["hand_on_part"] is False
    frames.append({"t": 2.0, "part": part, "hands": [(0.8, (150, 150, 260, 260))]})
    s = detect.summarise(frames, 0.25, 0.25)
    assert s["hand_on_part"] is True and s["frames"][2] == {"t": 2.0, "part": 0.6, "hand": 0.8, "hand_on_part": True}
    assert detect.summarise([], 0.25, 0.25)["part_seen"] is False


def test_hand_check_is_off_without_a_cutoff_but_its_scores_are_kept():
    frames = [{"t": 0.0, "part": [("capacitor", 0.6, (100, 100, 200, 200))], "hands": [(0.04, (150, 150, 260, 260))]}]
    s = detect.summarise(frames, 0.25, None)
    assert s["part_seen"] is True and s["hand_on_part"] is None
    assert s["frames"] == [{"t": 0.0, "part": 0.6, "hand": 0.04, "hand_on_part": None}]
    assert detect.summarise(frames, 0.25, 0.03)["hand_on_part"] is True  # once a cut-off is set it applies
    assert detect.summarise(frames, 0.25, 0.05)["hand_on_part"] is False


def test_cutoffs_drop_weak_parts_and_hands_on_them():
    frames = [{"t": 0.0, "part": [("capacitor", 0.1, (0, 0, 50, 50)), ("capacitor", 0.3, (200, 200, 260, 260))],
               "hands": [(0.9, (10, 10, 40, 40))]}]  # a strong hand, but only on the weak part box
    r = detect.frame_result(frames[0], 0.25, 0.25)
    assert r == {"t": 0.0, "part": 0.3, "hand": None, "hand_on_part": False}
    assert detect.frame_result(frames[0], 0.05, 0.25)["hand_on_part"] is True
    assert detect.frame_result(frames[0], 0.5, None) == {"t": 0.0, "part": None, "hand": None, "hand_on_part": None}


class FakeBoxes:
    def __init__(self, rows):
        self.xyxy = _T([r[0] for r in rows])
        self.cls = _T([r[1] for r in rows])
        self.conf = _T([r[2] for r in rows])


class _T(list):
    def tolist(self):
        return list(self)


class FakeYoloe:
    """Stands in for YOLOE: class 0 is the first label set, the last class is the hand."""

    def __init__(self):
        self.names = None

    def set_classes(self, names, embeddings):
        self.names = names

    def predict(self, img, conf, verbose):
        self.asked_conf = conf
        hand = len(self.names) - 1
        return [type("R", (), {"boxes": FakeBoxes([((10, 10, 50, 50), 0, 0.7), ((30, 30, 80, 80), hand, 0.8)])})()]


def test_yoloe_detector_wiring_with_a_stand_in_model():
    import torch

    d = object.__new__(detect.YoloeDetector)
    d.model, d.conf, d.hand_conf, d.lock = FakeYoloe(), 0.25, 0.25, __import__("threading").Lock()
    d.labels, d.embeddings = ["capacitor", "hand", "copper coil"], torch.zeros(1, 3, 4)
    img = np.zeros((90, 90, 3), np.uint8)
    out = d.check([(0.0, img), (1.0, img)], ["capacitor", "electric motor"])  # one label not prepared
    assert d.model.names == ["capacitor", "hand"] and d.model.asked_conf == detect.FLOOR
    assert out["part_seen"] and out["hand_on_part"] and len(out["frames"]) == 2
    assert d.check([(0.0, img)], ["ball bearing"])["part_seen"] is None  # no prepared label: not checked
    d.hand_conf = None  # the default until labelled frames set it
    out = d.check([(0.0, img)], ["capacitor"])
    assert out["part_seen"] is True and out["hand_on_part"] is None and out["frames"][0]["hand"] == 0.8


def test_detector_falls_back_when_models_are_missing_or_switched_off(monkeypatch, tmp_path):
    assert isinstance(detect.detector(), detect.NoDetector)  # switched off by the fixture
    monkeypatch.setenv("HUNAR_CLIP_DETECTOR", "yoloe")
    monkeypatch.setattr(detect, "DATA", tmp_path)  # no models in this folder
    detect.detector.cache_clear()
    assert isinstance(detect.detector(), detect.NoDetector)


def test_clip_frames_are_stored_and_returned(client, fake_speech, monkeypatch):
    class Seen:
        name = "stand-in"

        def check(self, samples, labels):
            return {"part_seen": True, "hand_on_part": True, "frames": [{"t": 0.0, "part": 0.7, "hand_on_part": True}]}

    monkeypatch.setattr(detect, "detector", lambda: Seen())
    aid = _fan_assessment(client)
    clip = _upload(client, aid).json()
    assert clip["detector"] == "stand-in" and clip["frames"][0]["hand_on_part"] is True
    pre = {p["criterion_id"]: p for p in client.get(f"/api/assessments/{aid}/prescores").json()
           if p["task_id"] == "fan2_parts"}
    assert pre["c2_cap_explain"]["suggested_level"] == 2  # explained, and the part was handled on camera


def _eval_script():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("eval_clips", Path(__file__).parents[1] / "scripts" / "eval_clip_detector.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_eval_scores_handle_empty_and_one_sided_cases():
    ev = _eval_script()
    s = ev.scores([(True, True), (True, False), (False, True), (False, False)])
    assert (s["tp"], s["fp"], s["fn"], s["precision"], s["recall"], s["f1"], s["accuracy"]) == (1, 1, 1, 0.5, 0.5, 0.5, 0.5)
    none_said = ev.scores([(True, False), (True, False)])  # positives, nothing predicted
    assert none_said["precision"] is None and none_said["recall"] == 0 and none_said["f1"] == 0
    assert ev.scores([(False, False)])["f1"] is None and ev.scores([])["accuracy"] is None


def test_eval_sweep_finds_the_hand_cutoff_from_labels():
    ev = _eval_script()
    box = (0, 0, 50, 50)
    frame = lambda hand: [{"t": 0.0, "part": [("capacitor", 0.6, box)], "hands": [(hand, box)]}]  # noqa: E731
    items = [(True, True, frame(0.04)), (True, True, frame(0.06)), (True, False, frame(0.02)), (True, False, frame(0.01))]
    out = ev.sweep(items, 0.25)
    by = {r["cutoff"]: r for r in out["hand_by_cutoff"]}
    assert by[0.03]["f1"] == 1.0 and by[0.01]["fp"] == 2 and by[0.05]["fn"] == 1
    assert out["best_f1_cutoff"]["hand"] == 0.03


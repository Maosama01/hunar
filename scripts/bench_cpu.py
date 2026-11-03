"""CPU speed and memory of the server-side work per assessment (`make bench`).

Measures, on the machine it runs on:

* the photo upload path of hunar.api.services.add_evidence without the database: decode, face blur,
  JPEG encode, perceptual hashes, detector. Input = PPE dataset images resized to the 1280 px long
  side and JPEG quality 85, which is what the PWA uploads (frontend/src/photo.ts).
* the reuse check against N stored photos: the old full scan, and the band-indexed lookup the API uses
  (hunar.api.services.find_reuse), plus how many candidates the index returns on real PPE hashes.
* the M1 mapper per declaration (MiniLM and LaBSE).
* faster-whisper small (int8) with the settings of hunar.speech.transcribe, as processing seconds
  per second of audio.

Each part runs with 1 thread (core seconds of work, for capacity planning) and 4 threads (the
latency a user sees on a 4 vCPU server). Writes experiments/bench_cpu.json.

LIMITS: speed and memory only, nothing about accuracy. A laptop core is usually faster than a cloud
vCPU, so re-run this on the server you plan to rent before sizing. Audio and declarations are
SYNTHETIC (text to speech, AI-written text); photos are a real public dataset.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

TRAINED = ROOT / "data" / "models" / "hunar_ppe_tools_yolov8n.pt"
PHOTOS = ROOT / "data" / "raw" / "ppe" / "test"
AUDIO = ROOT / "data" / "raw" / "voice_tts"
DECLARATIONS = ROOT / "data" / "synthetic" / "declarations_synthetic.csv"
OUT = ROOT / "experiments" / "bench_cpu.json"
MAX_DIM, JPEG_Q = 1280, 85  # frontend/src/photo.ts


def stats(seconds: list[float]) -> dict:
    s = sorted(seconds)
    return {"median_ms": round(1000 * s[len(s) // 2], 1), "p90_ms": round(1000 * s[int(0.9 * (len(s) - 1))], 1),
            "mean_ms": round(1000 * sum(s) / len(s), 1), "n": len(s)}


def rss_mb() -> float:
    import psutil

    return round(psutil.Process().memory_info().rss / 1e6)


def set_threads(n: int) -> None:
    import cv2
    import torch

    torch.set_num_threads(n)
    cv2.setNumThreads(n)


def machine() -> dict:
    cpu = platform.processor()
    try:
        if sys.platform == "darwin":
            cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        elif Path("/proc/cpuinfo").exists():
            cpu = next(ln.split(":", 1)[1].strip() for ln in Path("/proc/cpuinfo").read_text().splitlines()
                       if ln.startswith("model name"))
    except Exception:
        pass
    import psutil

    return {"cpu": cpu, "logical_cpus": os.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
            "os": platform.platform()}


def upload_jpegs(n: int) -> list[bytes]:
    """Dataset photos as the PWA would upload them."""
    import cv2

    out = []
    for p in sorted(PHOTOS.glob("*.jpg"))[:n]:
        img = cv2.imread(str(p))
        scale = MAX_DIM / max(img.shape[:2])
        img = cv2.resize(img, (round(img.shape[1] * scale), round(img.shape[0] * scale)), interpolation=cv2.INTER_CUBIC)
        out.append(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_Q])[1].tobytes())
    return out


def bench_photos(jpegs: list[bytes], threads: int) -> dict:
    from hunar.evidence import detector, hashing, privacy

    set_threads(threads)
    for data in jpegs[:3]:  # warm up
        detector.detect(privacy.decode(data), "warmup")
    stages = {k: [] for k in ("decode", "blur_faces", "encode_jpeg", "hash", "detect", "total")}
    for i, data in enumerate(jpegs):
        t0 = time.perf_counter()
        img = privacy.decode(data)
        t1 = time.perf_counter()
        blurred, _ = privacy.blur_faces(img)
        t2 = time.perf_counter()
        privacy.encode_jpeg(blurred)
        t3 = time.perf_counter()
        hashing.hashes_from_bgr(blurred)
        t4 = time.perf_counter()
        detector.detect(blurred, f"p{i}")
        t5 = time.perf_counter()
        for k, v in zip(stages, (t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4, t5 - t0), strict=True):
            stages[k].append(v)
    return {k: stats(v) for k, v in stages.items()}


def _reuse_db(path: Path, hashes: list[str]):
    """Throwaway SQLite file holding `hashes` as band-indexed photos of one assessment ("stored")."""
    from sqlalchemy import insert
    from sqlmodel import Session, SQLModel, create_engine

    from hunar.api.models import Assessment, EvidenceItem, PhashBand, Worker
    from hunar.evidence import hashing

    path.unlink(missing_ok=True)
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    now = dt.datetime.now(dt.UTC)
    with Session(engine) as s:
        s.add(Worker(id="w", code="W000"))
        s.add_all([Assessment(id="stored", worker_id="w"), Assessment(id="new", worker_id="w")])
        s.commit()
        conn = s.connection()
        for start in range(0, len(hashes), 100_000):
            chunk = list(enumerate(hashes[start:start + 100_000], start + 1))
            conn.execute(insert(EvidenceItem), [
                {"id": i, "assessment_id": "stored", "task_id": "t", "photo_id": "p", "stored_path": "",
                 "sha256": "", "phash": h, "dhash": h, "faces_blurred": 0, "detector_status": "unavailable",
                 "consent_confirmed": True, "created_at": now} for i, h in chunk])
            conn.execute(insert(PhashBand), [{"evidence_id": i, "band": b, "value": v} for i, h in chunk
                                             for b, v in enumerate(hashing.phash_bands(h))])
        s.commit()
    return engine


def _lookups(engine, queries: list[str], warmup: list[str]) -> tuple[list[float], list[float]]:
    """Times of hunar.api.services.find_reuse for `queries` right after the build (cold cache), and
    again after the `warmup` lookups (warm cache, as on a server that keeps answering)."""
    from sqlmodel import Session

    from hunar.api import services

    def run(qs: list[str]) -> list[float]:
        out = []
        for q in qs:
            t0 = time.perf_counter()
            services.find_reuse(s, "new", q)
            out.append(time.perf_counter() - t0)
        return out

    with Session(engine) as s:
        cold = run(queries)
        run(warmup)
        warm = run(queries)
    engine.dispose()
    return cold, warm


def bench_duplicates(sizes: list[int], db_dir: Path, queries: int = 20, warmup: int = 200) -> dict:
    """One reuse lookup against N stored photos with random hashes, in ms: a full scan with imagehash's
    distance as the API did before the band index (the query is parsed once here, so it slightly
    understates the old cost; the database read is not included), the same scan with the fast distance,
    and the indexed lookup the API uses now (hunar.api.services.find_reuse on a SQLite file), cold and warm."""
    import imagehash

    from hunar.evidence import hashing

    rng = random.Random(0)
    out = {}
    for n in sizes:
        hashes = [f"{rng.getrandbits(64):016x}" for _ in range(n)]
        query = f"{rng.getrandbits(64):016x}"
        t0 = time.perf_counter()
        q = imagehash.hex_to_hash(query)
        for h in hashes:
            int(q - imagehash.hex_to_hash(h))
        old = time.perf_counter() - t0
        t0 = time.perf_counter()
        hashing.find_duplicate(query, list(enumerate(hashes, 1)))
        fast = time.perf_counter() - t0
        path = db_dir / f"bench_reuse_{n}.db"
        cold, warm = _lookups(_reuse_db(path, hashes), [f"{rng.getrandbits(64):016x}" for _ in range(queries)],
                              [f"{rng.getrandbits(64):016x}" for _ in range(warmup)])
        path.unlink(missing_ok=True)
        out[str(n)] = {"full_scan_before_ms": round(1000 * old, 1), "full_scan_fast_distance_ms": round(1000 * fast, 1),
                       "indexed_cold_ms": stats(cold), "indexed_warm_ms": stats(warm)}
    return out


def real_hashes(db_dir: Path, queries: int = 20, warmup: int = 200) -> dict | None:
    """The band index on the real pHashes of the PPE dataset (data/raw/ppe/phash_cache.json, `make
    ppe-split`), which are less uniform than random hashes: candidates read per lookup, and the warm
    lookup time when each stored photo is submitted again for another worker."""
    from collections import defaultdict

    from hunar.evidence import hashing

    cache = PHOTOS.parent / "phash_cache.json"
    if not cache.exists():
        return None
    hashes = [f"{v:016x}" for v in json.loads(cache.read_text()).values()]
    index = defaultdict(set)
    for i, h in enumerate(hashes):
        for b, v in enumerate(hashing.phash_bands(h)):
            index[(b, v)].add(i)
    counts = sorted(len(set().union(*(index[(b, v)] for b, v in enumerate(hashing.phash_bands(h)))) - {i})
                    for i, h in enumerate(hashes))
    rng = random.Random(0)
    path = db_dir / "bench_reuse_real.db"
    _, warm = _lookups(_reuse_db(path, hashes), rng.sample(hashes, queries), rng.choices(hashes, k=warmup))
    path.unlink(missing_ok=True)
    return {"data_kind": "real_public_dataset", "stored_photos": len(hashes),
            "candidates_mean": round(sum(counts) / len(counts), 1), "candidates_median": counts[len(counts) // 2],
            "candidates_p90": counts[int(0.9 * (len(counts) - 1))], "candidates_max": counts[-1],
            "indexed_warm_ms": stats(warm)}


def bench_mapper(name: str, texts: list[str], threads: list[int]) -> dict:
    from hunar.mapper.mapper import QPMapper

    t0 = time.perf_counter()
    m = QPMapper(name)
    res = {"load_and_fit_s": round(time.perf_counter() - t0, 2), "criteria": len(m._rows), "packs": len(m.packs),
           "by_threads": {}}
    for n in threads:
        set_threads(n)
        m.map(texts[0])
        times = []
        for t in texts:
            t0 = time.perf_counter()
            m.map(t)
            times.append(time.perf_counter() - t0)
        res["by_threads"][str(n)] = stats(times)
    return res


def bench_speech(files: list[Path], threads: int) -> dict:
    from faster_whisper import WhisperModel

    from hunar.speech.transcribe import MODEL

    t0 = time.perf_counter()
    model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=threads)
    load = time.perf_counter() - t0
    audio = proc = 0.0
    for f in files:
        lang = "hi" if "Lekha" in f.name else "en"
        t0 = time.perf_counter()
        segments, info = model.transcribe(str(f), language=lang, beam_size=5, vad_filter=True,
                                          condition_on_previous_text=False)
        list(segments)  # decoding is lazy
        proc += time.perf_counter() - t0
        audio += info.duration
    return {"model": f"faster-whisper-{MODEL} int8", "load_s": round(load, 2), "files": len(files),
            "audio_s": round(audio, 1), "processing_s": round(proc, 1),
            "processing_s_per_audio_s": round(proc / audio, 3), "rss_mb_after_load_and_run": rss_mb()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--weights", type=Path, default=TRAINED,
                    help="YOLO weights; defaults to the trained Hunar detector")
    ap.add_argument("--threads", type=int, nargs="+", default=[1, 4])
    ap.add_argument("--photos", type=int, default=100)
    ap.add_argument("--audio", type=int, default=20, help="number of text-to-speech files")
    ap.add_argument("--declarations", type=int, default=50)
    ap.add_argument("--dup-sizes", type=int, nargs="+", default=[1_000, 10_000, 100_000, 1_000_000])
    ap.add_argument("--db-dir", type=Path, default=Path(tempfile.gettempdir()),
                    help="where the throwaway SQLite files for the reuse lookup go")
    args = ap.parse_args()
    if not args.weights.exists():
        sys.exit(f"weights not found: {args.weights} (train in Colab, or pass --weights <path to yolov8n.pt>, "
                 "the COCO-pretrained model of the same size that the Colab notebook downloads)")
    os.environ["HUNAR_YOLO_WEIGHTS"] = str(args.weights)  # read when hunar.evidence.detector is imported

    from hunar.mapper.evaluate import git_commit, load_dataset
    from hunar.mapper.matchers import _usable_hf_home

    _usable_hf_home()
    mem = {"baseline": rss_mb()}
    jpegs = upload_jpegs(args.photos)
    photos = {"data_kind": "real_public_dataset",
              "dataset": "keremberke/protective-equipment-detection test split (CC BY 4.0)",
              "input": f"first {len(jpegs)} images, resized to {MAX_DIM} px long side, JPEG quality {JPEG_Q}",
              "mean_upload_kb": round(sum(map(len, jpegs)) / len(jpegs) / 1024, 1),
              "weights": args.weights.name, "weights_sha256": hashlib.sha256(args.weights.read_bytes()).hexdigest(),
              "by_threads": {}}
    if args.weights.resolve() != TRAINED.resolve():
        photos["weights_note"] = ("not the trained Hunar detector: same YOLOv8n architecture and input size, "
                                  "so speed is comparable; its detections are ignored")
    for n in args.threads:
        photos["by_threads"][str(n)] = bench_photos(jpegs, n)
    mem["after_detector"] = rss_mb()

    dups = {"data_kind": "synthetic", "input": "random 64-bit hashes; time of one reuse lookup, in ms",
            "by_stored_photos": bench_duplicates(args.dup_sizes, args.db_dir),
            "real_hashes": real_hashes(args.db_dir)}

    texts = [r["text"] for r in load_dataset(DECLARATIONS)][:args.declarations]
    mapper = {"data_kind": "synthetic", "input": f"{len(texts)} AI-written declarations (data/synthetic/)"}
    for name in ("minilm", "labse"):
        mapper[name] = bench_mapper(name, texts, args.threads)
        mem[f"after_{name}"] = rss_mb()

    files = sorted(AUDIO.glob("*.aiff"))[:args.audio]
    speech = {"data_kind": "synthetic", "input": "macOS text-to-speech audio (data/raw/voice_tts/)",
              "settings": "beam_size=5, vad_filter=True, language from the voice (as hunar.speech.transcribe)",
              "by_threads": {str(n): bench_speech(files, n) for n in args.threads}}

    versions = {p: importlib.metadata.version(p) for p in
                ("ultralytics", "torch", "opencv-python-headless", "sentence-transformers", "faster-whisper",
                 "ctranslate2") if _installed(p)}
    out = {"experiment": "bench_cpu", "data_kind": "mixed (see each part)",
           "command": "uv run python scripts/bench_cpu.py " + " ".join(sys.argv[1:]),
           "created": dt.datetime.now().isoformat(timespec="seconds"), "git_commit": git_commit(),
           "machine": machine(), "versions": versions,
           "note": ("Speed and memory only, nothing about accuracy. 1 thread = core seconds of work (capacity "
                    "planning); 4 threads = latency on a 4 vCPU server. A laptop core is usually faster than a "
                    "cloud vCPU: re-run on the target server before sizing."),
           "photo_pipeline": photos, "duplicate_search": dups, "mapper": mapper, "speech": speech,
           "rss_mb": mem}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _installed(pkg: str) -> bool:
    try:
        importlib.metadata.version(pkg)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


if __name__ == "__main__":
    main()

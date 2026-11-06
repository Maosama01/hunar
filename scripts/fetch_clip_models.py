"""Download the frame detector for guided clips and prepare its text prompts (`make clip-models`).

1. yoloe-11s-seg.pt: Ultralytics YOLOE, an open-vocabulary detector (AGPL-3.0, like the ultralytics
   package Hunar already uses), from the ultralytics/assets GitHub release, into data/models/;
2. mobileclip_blt.ts: the MobileCLIP text encoder YOLOE uses for text prompts (same release);
3. yoloe_text_pe.pt: text embeddings for every `detect` label in the rubric clips plus "hand", so
   the app never needs the text encoder or the `clip` tokenizer at runtime.

The `clip` tokenizer is only needed here. The Makefile runs this script with
`uv run --with "clip @ git+https://github.com/ultralytics/CLIP.git@<commit>"`, so the project
environment does not change. Re-run it after adding a new `detect` label to a rubric file. Prints the
size and SHA-256 of each file (data/models/ is gitignored).
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from hunar.paths import DATA  # noqa: E402
from hunar.rubric.engine import load_tasks  # noqa: E402
from hunar.video.detect import HAND, PE_FILE, WEIGHTS  # noqa: E402

MODELS = DATA / "models"


def labels() -> list[str]:
    out = {HAND}
    for t in load_tasks():
        for c in t.clips:
            out.update(c.detect)
    return sorted(out)


def main() -> int:
    import torch
    from ultralytics import YOLOE

    MODELS.mkdir(parents=True, exist_ok=True)
    os.chdir(MODELS)  # ultralytics saves the assets it downloads in the working directory
    model = YOLOE(WEIGHTS)
    names = labels()
    pe = model.get_text_pe(names)  # downloads mobileclip_blt.ts on first use
    torch.save({"labels": names, "embeddings": pe.detach().cpu(), "weights": WEIGHTS}, MODELS / PE_FILE)
    print(f"text prompts for {len(names)} labels: {', '.join(names)}")
    for f in (WEIGHTS, "mobileclip_blt.ts", PE_FILE):
        p = MODELS / f
        if p.exists():
            print(f"{f}: {p.stat().st_size:,} bytes, sha256 {hashlib.sha256(p.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

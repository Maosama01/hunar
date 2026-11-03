"""Download splits of the public PPE dataset used for M2.

    uv run python scripts/fetch_ppe_test.py                 # test split only (hashing evaluation)
    uv run python scripts/fetch_ppe_test.py train valid test  # all splits (re-split check)

Dataset: "Personal Protective Equipment" (Roboflow export v7, 11,978 images, CC BY 4.0),
mirrored on Hugging Face as keremberke/protective-equipment-detection. See docs/DATA.md.
Images go to data/raw/ppe/<split>/ (gitignored). Zips are deleted after extraction to save disk.
"""
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://huggingface.co/datasets/keremberke/protective-equipment-detection/resolve/main/data/"
DEST = ROOT / "data" / "raw" / "ppe"


def fetch(split: str) -> None:
    out = DEST / split
    if out.exists() and (out / "_annotations.coco.json").exists():
        n = sum(1 for p in out.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        print(f"{split}: already present ({n} images)")
        return
    z = DEST / f"{split}.zip"
    print("downloading", BASE + f"{split}.zip")
    urllib.request.urlretrieve(BASE + f"{split}.zip", z)
    h = hashlib.sha256()
    with z.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print(f"{split}: zip sha256 {h.hexdigest()}")
    with zipfile.ZipFile(z) as f:
        f.extractall(out)
    z.unlink()
    n = sum(1 for p in out.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    print(f"{split}: {n} images in {out.relative_to(ROOT)}")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for split in sys.argv[1:] or ["test"]:
        fetch(split)
    return 0


if __name__ == "__main__":
    sys.exit(main())

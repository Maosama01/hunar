"""Download the test split of the public PPE dataset used for the M2 hashing evaluation.

Dataset: "Personal Protective Equipment" (Roboflow export v7, 11,978 images, CC BY 4.0),
mirrored on Hugging Face as keremberke/protective-equipment-detection. See docs/DATA.md.
Images go to data/raw/ppe/test/ (gitignored).
"""
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://huggingface.co/datasets/keremberke/protective-equipment-detection/resolve/main/data/test.zip"
DEST = ROOT / "data" / "raw" / "ppe"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    z = DEST / "test.zip"
    if not z.exists():
        print("downloading", URL)
        urllib.request.urlretrieve(URL, z)
    print("sha256", hashlib.sha256(z.read_bytes()).hexdigest())
    out = DEST / "test"
    if not out.exists():
        with zipfile.ZipFile(z) as f:
            f.extractall(out)
    n = sum(1 for p in out.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    print(f"{n} images in {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

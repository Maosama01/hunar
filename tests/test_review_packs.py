"""Review packs for the experts (scripts/make_review_packs.py)."""
import csv
import importlib.util
import json
from pathlib import Path

from hunar.quiz import bank as banks
from hunar.rubric.engine import load_tasks

ROOT = Path(__file__).parents[1]


def _packs():
    spec = importlib.util.spec_from_file_location("make_review_packs", ROOT / "scripts" / "make_review_packs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_packs_cover_every_question_task_and_text(tmp_path):
    mod = _packs()
    assert mod.main(["--out", str(tmp_path)]) == 0
    for trade in banks.trades():
        b = banks.load(trade)
        rows = _rows(tmp_path / f"quiz_{trade}.csv")
        assert [r["item_id"] for r in rows] == [it.id for it in sorted(b.items, key=lambda i: list(b.nos).index(i.nos))]
        assert all(r["verdict"] == "" for r in rows)
        page = (tmp_path / f"quiz_{trade}.html").read_text(encoding="utf-8")
        assert all(it.id in page and it.stem.hi in page for it in b.items)
    tasks = load_tasks()
    for trade in {t.trade for t in tasks}:
        rows = _rows(tmp_path / f"rubric_{trade}.csv")
        mine = [t for t in tasks if t.trade == trade]
        assert sum(r["kind"] == "criterion" for r in rows) == sum(len(t.criteria) for t in mine)
        assert sum(r["kind"] == "clip" for r in rows) == sum(len(t.clips) for t in mine)
    en = json.loads((ROOT / "frontend" / "src" / "i18n" / "locales" / "en.json").read_text(encoding="utf-8"))
    ui = _rows(tmp_path / "ui_hindi.csv")
    assert len(ui) == len(en) and all(r["hindi"] for r in ui)


def test_summary_counts_returned_verdicts(tmp_path):
    mod = _packs()
    returned, out = tmp_path / "review", tmp_path / "experiments"
    returned.mkdir()
    mod.write_csv(returned / "quiz_electrician_E1.csv", mod.QUIZ_FIELDS, [
        {"item_id": "el-001", "verdict": "ok", "hindi": "ok", "difficulty": "easy"},
        {"item_id": "el-002", "verdict": "Fix", "hindi": "ok", "difficulty": "hard"},
        {"item_id": "el-003", "verdict": "", "hindi": "", "difficulty": ""},
    ])
    mod.write_csv(returned / "ui_hindi_H1.csv", mod.UI_FIELDS, [{"key": "a", "verdict": "ok"}])
    assert mod.summary(returned, out) == 0
    res = json.loads((out / "expert_review.json").read_text(encoding="utf-8"))
    assert res["data_kind"] == "real" and res["n_sheets"] == 2 and res["n_reviewers"] == 2
    quiz = next(s for s in res["sheets"] if s["sheet"] == "quiz_electrician")
    assert quiz["reviewer"] == "E1" and quiz["verdict"] == {"fix": 1, "not marked": 1, "ok": 1}
    assert quiz["difficulty"] == {"easy": 1, "hard": 1, "not marked": 1}


def test_summary_is_pending_without_returned_sheets(tmp_path, capsys):
    mod = _packs()
    assert mod.summary(tmp_path, tmp_path / "experiments") == 0
    assert "RESULT PENDING" in capsys.readouterr().out
    assert not (tmp_path / "experiments").exists()

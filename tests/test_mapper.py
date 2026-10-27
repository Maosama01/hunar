import numpy as np
import pytest

from hunar.mapper.evaluate import tie_aware
from hunar.mapper.mapper import QPMapper
from hunar.mapper.text import split_sentences, tokens


def test_split_sentences_handles_devanagari_danda_and_newlines():
    parts = split_sentences("मैं वायरिंग करता हूँ। मीटर भी लगाता हूँ\nI fix switch boards.")
    assert parts == ["मैं वायरिंग करता हूँ", "मीटर भी लगाता हूँ", "I fix switch boards"]


def test_tokens_drop_stop_words_and_stem():
    assert tokens("I am fixing the wires and switches") == ["fix", "wir", "switch"]


@pytest.mark.parametrize(
    "scores,gold,expected",
    [
        ([0.9, 0.5, 0.1], 0, {"top1": 1.0, "top3": 1.0, "rr": 1.0}),
        ([0.1, 0.5, 0.9], 0, {"top1": 0.0, "top3": 1.0, "rr": 1 / 3}),
        # All tied (e.g. a keyword baseline on Devanagari text): chance credit only.
        ([0.0, 0.0, 0.0, 0.0, 0.0], 0, {"top1": 0.2, "top3": 0.6, "rr": np.mean(1 / np.arange(1, 6))}),
        ([0.5, 0.5, 0.1], 1, {"top1": 0.5, "top3": 1.0, "rr": 0.75}),
    ],
)
def test_tie_aware_metrics(scores, gold, expected):
    m = tie_aware(np.array(scores), gold)
    for k, v in expected.items():
        assert m[k] == pytest.approx(v)


def test_mapper_ranks_stub_pack_and_explains(stub_qp):
    mapper = QPMapper("keyword", packs=[stub_qp])
    res = mapper.map("I connect the switch and lamp holder. I check continuity with a multimeter.")
    top = res.ranking[0]
    assert top.nqr_id == 0 and top.score > 0
    assert any(m.pc_id == "STUB/N0001.PC2" for m in top.matched)
    # Safety criteria were not mentioned, so they are reported as gaps.
    assert {g.pc_id for g in top.gaps} >= {"STUB/N0002.PC1"}
    assert "Suggestion only" in res.note


def test_tfidf_baseline_prefers_solar_pack_for_solar_text():
    mapper = QPMapper("tfidf")
    ranked = mapper.rank("I install solar panels on rooftops and connect the inverter and battery bank.")
    assert ranked[0] == 11371

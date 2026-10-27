"""Checks of the M4 analysis maths on SIMULATED ratings. Simulation lives only in these tests;
it is never written to experiments/ or presented as a study result."""
import numpy as np
import pandas as pd
import pytest

from hunar.study.analyse import alpha, analyse, fleiss, matrix, pairwise


def sim(levels_by_rater: dict[str, list[int]], condition="unassisted"):
    rows = []
    for r, levels in levels_by_rater.items():
        for i, lv in enumerate(levels):
            rows.append({"rater_id": r, "item_id": f"I{i}", "condition": condition, "level": lv, "is_sample": False})
    return pd.DataFrame(rows)


def test_perfect_agreement():
    m = matrix(sim({"R1": [0, 1, 2, 3, 2], "R2": [0, 1, 2, 3, 2], "R3": [0, 1, 2, 3, 2]}))
    assert fleiss(m) == pytest.approx(1.0)
    assert alpha(m) == pytest.approx(1.0)
    assert pairwise(m) == (1.0, 1.0)


def test_known_fleiss_kappa_value():
    # Hand-computed: 4 items, 2 raters, categories 0/1.
    # Items: (0,0), (1,1), (0,1), (1,1) -> P_bar = (1+1+0+1)/4 = 0.75; p0 = 3/8, p1 = 5/8;
    # P_e = 9/64 + 25/64 = 34/64; kappa = (0.75 - 0.53125) / (1 - 0.53125) = 0.4667
    m = matrix(sim({"R1": [0, 1, 0, 1], "R2": [0, 1, 1, 1]}))
    assert fleiss(m) == pytest.approx(0.21875 / 0.46875)


def test_random_ratings_have_near_zero_agreement():
    rng = np.random.default_rng(0)
    m = matrix(sim({f"R{k}": rng.integers(0, 4, 400).tolist() for k in range(4)}))
    assert abs(fleiss(m)) < 0.05 and abs(alpha(m)) < 0.05


def test_alpha_handles_missing_ratings():
    m = matrix(sim({"R1": [0, 1, 2, 3], "R2": [0, 1, 2, 3]}))
    m.loc["I3", "R2"] = np.nan
    assert alpha(m) == pytest.approx(1.0)


def test_sample_items_are_excluded_and_difference_reported():
    rng = np.random.default_rng(1)
    truth = rng.integers(0, 4, 30)
    un = sim({f"R{k}": np.clip(truth + rng.integers(-2, 3, 30), 0, 3).tolist() for k in range(3)}, "unassisted")
    asst = sim({f"R{k}": np.clip(truth + rng.integers(-1, 2, 30) * (rng.random(30) < 0.3), 0, 3).tolist()
                for k in range(3)}, "assisted")
    sample = pd.DataFrame([{"rater_id": "R0", "item_id": "S1", "condition": "assisted", "level": 3, "is_sample": True}])
    res = analyse(pd.concat([un, asst, sample]), n_boot=200)
    assert res["n_ratings"] == 180
    assert res["conditions"]["assisted"]["n_items"] == 30
    d = res["difference"]
    assert d["items_in_both"] == 30 and d["alpha_assisted_minus_unassisted"] > 0

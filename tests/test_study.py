"""Checks of the M4 analysis maths on SIMULATED ratings. Simulated ratings appear only in these tests
and in the clearly labelled design simulation (hunar.study.design_sim); they never reach the study
result, experiments/m4_consistency.json."""
import numpy as np
import pandas as pd
import pytest

from hunar.study import design_sim as ds
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


# ---- fast statistics used by the design simulation ---------------------------------------------


@pytest.mark.parametrize("seed", range(5))
def test_fast_alpha_and_kappa_match_reference_packages(seed):
    rng = np.random.default_rng(seed)
    truth = rng.integers(0, 4, 25)
    ratings = np.clip(truth[:, None] + rng.integers(-1, 2, (25, 2 + seed % 4)), 0, 3)
    m = pd.DataFrame(ratings, columns=[f"R{k}" for k in range(ratings.shape[1])])
    assert ds.alpha_ordinal(ratings) == pytest.approx(alpha(m), abs=1e-9)
    assert ds.fleiss_kappa_counts(ds.category_counts(ratings)) == pytest.approx(fleiss(m), abs=1e-9)


def test_bootstrap_weights_equal_duplicated_items():
    rng = np.random.default_rng(3)
    ratings = rng.integers(0, 4, (10, 3))
    w = np.array([[2, 0, 1, 1, 0, 3, 1, 0, 1, 1]])
    dup = np.repeat(ratings, w[0], axis=0)
    assert ds.alpha_ordinal_weighted(ds.category_counts(ratings), w)[0] == pytest.approx(ds.alpha_ordinal(dup))


def test_identical_ratings_give_alpha_one():
    assert ds.alpha_ordinal(np.full((6, 3), 2)) == 1.0


def test_calibration_hits_target_alpha():
    sigma = ds.calibrate(0.6, iters=25)
    assert ds.population_alpha(sigma, n_items=20000) == pytest.approx(0.6, abs=0.01)


def test_no_effect_scenario_rarely_detects():
    rng = np.random.default_rng(0)
    s = ds.calibrate(0.5, iters=25)
    cell = ds.run_cell(4, 25, s, s, reps=150, n_boot=300, rng=rng)
    assert cell["detected_share"] <= 0.08  # one-sided 2.5 % nominal; small reps

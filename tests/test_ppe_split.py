import numpy as np

from hunar.evidence.ppe_split import (
    NAMES,
    class_counts,
    cross_split_near_duplicates,
    group_near_duplicates,
    stratified_group_split,
)


def test_grouping_is_single_linkage_within_threshold():
    a = 0
    b = a ^ 0b111            # 3 bits from a
    c = b ^ (0b111 << 10)    # 3 bits from b, 6 from a (chained into a's group at threshold 4)
    far = (1 << 64) - 1      # 64 bits from a
    g = group_near_duplicates([a, b, c, far], max_dist=4)
    assert g[0] == g[1] == g[2] and g[3] != g[0]
    g2 = group_near_duplicates([a, b, c, far], max_dist=2)
    assert len(set(g2.tolist())) == 4


def test_split_keeps_groups_together_and_covers_every_class():
    rng = np.random.default_rng(0)
    pool, hashes = [], []
    for k in range(700):                      # 700 scenes x 3 near-identical frames
        cls = NAMES[k % 4] if k % 9 else NAMES[0]
        base = int(rng.integers(0, 2**62))
        for f in range(3):
            pool.append({"labels": [f"{NAMES.index(cls)} 0.5 0.5 0.1 0.1"], "classes": [cls]})
            hashes.append(base ^ (1 << f))    # 1-2 bits apart within a scene
    groups = group_near_duplicates(hashes, max_dist=4)
    assert len(set(groups.tolist())) == 700
    split = stratified_group_split(pool, groups, seed=0)
    by_group = {}
    for g, s in zip(groups, split, strict=True):
        by_group.setdefault(g, set()).add(s)
    assert all(len(v) == 1 for v in by_group.values()), "a scene must not straddle splits"
    counts = class_counts(pool, split)
    for s in ("train", "valid", "test"):
        assert all(counts[s]["boxes"][c] > 0 for c in NAMES), f"{s} misses a class"
    assert counts["train"]["images"] > counts["test"]["images"] > 0
    assert cross_split_near_duplicates(hashes, split, max_dist=4) == 0


def test_rare_class_in_two_groups_goes_to_train_and_test():
    """Like safety shoes in the PPE data: two videos only. One trains, the other tests."""
    pool, groups = [], []
    for g, (cls, n) in enumerate([("safety_shoes", 60), ("safety_shoes", 30)] +
                                 [(NAMES[k % 4 if k % 4 != 2 else 0], 5) for k in range(200)]):
        for _ in range(n):
            pool.append({"labels": [f"{NAMES.index(cls)} 0.5 0.5 0.1 0.1"], "classes": [cls]})
            groups.append(g)
    split = stratified_group_split(pool, np.array(groups), seed=0)
    shoes = {s for r, s in zip(pool, split, strict=True) if r["classes"] == ["safety_shoes"]}
    assert shoes == {"train", "test"}
    assert split[0] == "train" and split[60] == "test"

"""Tests for blind-tuning state and perturbation."""

import random

from earcurve.core.eq import BANDS, MAX_GAIN, MIN_GAIN, flat_curve
from earcurve.core.tuning import (
    TuningSession,
    make_mapping,
    make_queue,
    nonzero_bands,
    perturb_curve,
)


def test_perturb_changes_one_band_and_clamps() -> None:
    rng = random.Random(7)
    base = flat_curve()
    for index in range(len(BANDS)):
        candidate = perturb_curve(base, index, rng)
        changed = [
            pos
            for pos, (old, new) in enumerate(zip(base.bands, candidate.bands))
            if old.gain != new.gain
        ]
        assert changed == [index]
        assert abs(candidate.bands[index].gain) >= 0.5
        assert MIN_GAIN <= candidate.bands[index].gain <= MAX_GAIN
        assert all(band.gain == 0 for pos, band in enumerate(candidate.bands) if pos != index)


def test_perturb_at_limit_flips_direction() -> None:
    base = flat_curve()
    base.bands[0].gain = 12
    candidate = perturb_curve(base, 0, random.Random(3))
    assert candidate.bands[0].gain < 12
    assert candidate.bands[0].gain >= MIN_GAIN


def test_queue_covers_all_bands() -> None:
    queue = make_queue(24, random.Random(1))
    assert len(queue) == 24
    assert sorted(queue[:20]) == sorted(list(range(10)) * 2)
    assert all(0 <= index < 10 for index in queue)
    assert len(make_queue(12, random.Random(2))) == 12


def test_mapping_is_balanced_shape() -> None:
    for seed in range(20):
        mapping = make_mapping(random.Random(seed))
        assert set(mapping) == {1, 2}
        assert set(mapping.values()) == {"best", "cand"}


def test_session_records_and_converges() -> None:
    rng = random.Random(11)
    session = TuningSession(
        baseline=flat_curve(), best=flat_curve(), trials=4, queue=[0, 1, 2, 3]
    )
    picks = 0
    for _ in range(4):
        plan = session.next_plan(rng)
        assert plan is not None
        candidate_option = next(
            option for option, side in plan.mapping.items() if side == "cand"
        )
        finished = session.record(candidate_option, plan)
        picks += 1
        if finished:
            break
    assert picks == 4
    assert session.done == 4
    assert session.next_plan(rng) is None

    session.again(rng)
    assert session.done == 0
    assert session.baseline == session.best
    assert len(session.queue) >= 4


def test_skip_keeps_best() -> None:
    rng = random.Random(4)
    session = TuningSession(baseline=flat_curve(), best=flat_curve(), trials=2)
    plan = session.next_plan(rng)
    assert plan is not None
    before = [(band.gain, band.q) for band in session.best.bands]
    session.record("skip", plan)
    after = [(band.gain, band.q) for band in session.best.bands]
    assert before == after
    assert session.done == 1


def test_nonzero_bands() -> None:
    curve = flat_curve()
    assert nonzero_bands(curve) == 0
    curve.bands[3].gain = 1.5
    curve.bands[4].gain = -2
    assert nonzero_bands(curve) == 2

"""Blind A/B preference-tuning state.

The candidate in each trial is the current best curve with one band nudged by
1–3 dB. The user never sees which option is which.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .eq import BANDS, Curve, MAX_GAIN, MIN_GAIN, clamp, clone_curve, round1


@dataclass(frozen=True)
class TrialPlan:
    band_index: int
    candidate: Curve
    mapping: dict[int, str]  # option number -> "best" / "cand"


def make_queue(trials: int, rng: random.Random | None = None) -> list[int]:
    source = rng or random
    queue = list(range(len(BANDS))) + list(range(len(BANDS)))
    source.shuffle(queue)
    while len(queue) < trials:
        queue.append(source.randrange(len(BANDS)))
    return queue[: max(1, trials)]


def perturb_curve(
    curve: Curve, band_index: int, rng: random.Random | None = None
) -> Curve:
    source = rng or random
    candidate = clone_curve(curve)
    band = candidate.bands[band_index]
    delta = 1.0 + source.random() * 2.0
    if source.random() < 0.5:
        delta = -delta
    nxt = band.gain + delta
    if nxt > MAX_GAIN or nxt < MIN_GAIN:
        nxt = band.gain - delta
    nxt = round1(clamp(nxt, MIN_GAIN, MAX_GAIN))
    if abs(nxt - band.gain) < 0.5:
        nxt = round1(
            clamp(band.gain + (1 if delta > 0 else -1), MIN_GAIN, MAX_GAIN)
        )
    band.gain = nxt
    return candidate


def make_mapping(rng: random.Random | None = None) -> dict[int, str]:
    source = rng or random
    if source.random() < 0.5:
        return {1: "best", 2: "cand"}
    return {1: "cand", 2: "best"}


@dataclass
class TuningSession:
    baseline: Curve
    best: Curve
    trials: int = 24
    done: int = 0
    queue: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.best = clone_curve(self.best)
        if not self.queue:
            self.queue = make_queue(self.trials)

    def next_plan(self, rng: random.Random | None = None) -> TrialPlan | None:
        if self.done >= self.trials:
            return None
        source = rng or random
        index = (
            self.queue[self.done]
            if self.done < len(self.queue)
            else source.randrange(len(BANDS))
        )
        return TrialPlan(
            band_index=index,
            candidate=perturb_curve(self.best, index, source),
            mapping=make_mapping(source),
        )

    def record(self, choice: int | str, plan: TrialPlan) -> bool:
        """choice is 1, 2, or "skip"; returns True when the session is complete."""
        if choice in (1, 2) and plan.mapping.get(int(choice)) == "cand":
            self.best = clone_curve(plan.candidate)
        self.done += 1
        return self.done >= self.trials

    def again(self, rng: random.Random | None = None) -> None:
        self.baseline = clone_curve(self.best)
        self.done = 0
        self.queue = make_queue(self.trials, rng)


def nonzero_bands(curve: Curve) -> int:
    return sum(1 for band in curve.bands if abs(band.gain) > 0.05)

"""Small, deterministic statistical helpers for paper experiment reports."""

from __future__ import annotations

import math
import random
import statistics
from typing import Dict, List, Sequence, Tuple


def _require_samples(samples: Sequence[float]) -> List[float]:
    values = [float(value) for value in samples]
    if not values:
        raise ValueError("at least one sample is required")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("samples must contain only finite numbers")
    return values


def percentile(samples: Sequence[float], percentage: float) -> float:
    """Return a linearly interpolated percentile for finite samples."""
    values = sorted(_require_samples(samples))
    if percentage < 0.0 or percentage > 100.0:
        raise ValueError("percentage must be between 0 and 100")
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * (percentage / 100.0)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def describe_samples(samples: Sequence[float]) -> Dict[str, float]:
    """Describe a finite sample without hiding its size or spread."""
    values = _require_samples(samples)
    standard_deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "count": float(len(values)),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "standard_deviation": standard_deviation,
        "minimum": min(values),
        "maximum": max(values),
        "p50": percentile(values, 50.0),
        "p95": percentile(values, 95.0),
        "p99": percentile(values, 99.0),
    }


def bootstrap_mean_ci(
    samples: Sequence[float],
    *,
    seed: int,
    resamples: int = 2_000,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """Return a deterministic percentile bootstrap interval for the mean."""
    values = _require_samples(samples)
    if resamples < 100:
        raise ValueError("resamples must be at least 100")
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    randomizer = random.Random(seed)
    means = []
    for _ in range(resamples):
        drawn = [randomizer.choice(values) for _ in values]
        means.append(statistics.fmean(drawn))
    tail = (1.0 - confidence) / 2.0
    return (
        percentile(means, tail * 100.0),
        percentile(means, (1.0 - tail) * 100.0),
    )

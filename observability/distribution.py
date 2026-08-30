from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _finite(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    return array[np.isfinite(array)]


def _ks_statistic(left: np.ndarray, right: np.ndarray) -> float:
    """Two-sample Kolmogorov-Smirnov statistic without a scipy dependency."""
    points = np.sort(np.concatenate((left, right)))
    left_cdf = np.searchsorted(np.sort(left), points, side="right") / left.size
    right_cdf = np.searchsorted(np.sort(right), points, side="right") / right.size
    return float(np.max(np.abs(left_cdf - right_cdf)))


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    ratio_threshold: float = 3.0,
) -> dict[str, Any]:
    """Detect location and shape drift with robust effect size plus a KS test."""
    cur = _finite(current_values)
    base = _finite(baseline_values)
    if cur.size == 0 or base.size == 0:
        return {"is_anomaly": False, "score": 0.0, "method": "ks+robust_location", "reason": "empty_input"}

    ks = _ks_statistic(cur, base)
    # Approximate alpha=0.05 critical value.  For tiny samples the robust
    # location test remains useful when the asymptotic KS threshold exceeds 1.
    ks_critical = 1.36 * np.sqrt((cur.size + base.size) / (cur.size * base.size))

    base_median = float(np.median(base))
    cur_median = float(np.median(cur))
    base_mad = float(np.median(np.abs(base - base_median)))
    robust_scale = 1.4826 * base_mad
    if robust_scale == 0:
        # A stable baseline should treat any material displacement as signal.
        tolerance = max(abs(base_median) * 1e-9, 1e-12)
        location_score = float("inf") if abs(cur_median - base_median) > tolerance else 0.0
    else:
        location_score = abs(cur_median - base_median) / robust_scale

    ratio_score = 1.0
    if base_median != 0 and cur_median != 0:
        ratio_score = max(abs(cur_median / base_median), abs(base_median / cur_median))
    elif base_median != cur_median:
        ratio_score = float("inf")

    is_anomaly = ks > min(1.0, ks_critical) or location_score > 3.5 or ratio_score >= ratio_threshold
    score = max(ks / max(ks_critical, 1e-12), location_score / 3.5, ratio_score / ratio_threshold)
    return {
        "is_anomaly": bool(is_anomaly),
        "score": float(score),
        "method": "ks+robust_location",
        "reason": (
            f"ks={ks:.4f}, ks_critical={ks_critical:.4f}, "
            f"baseline_median={base_median:.3f}, current_median={cur_median:.3f}, "
            f"robust_location_score={location_score:.3f}"
        ),
        "ks_statistic": ks,
        "location_score": float(location_score),
    }

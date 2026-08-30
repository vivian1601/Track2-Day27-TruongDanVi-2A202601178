"""Anomaly detection starter.

Z-score is deliberately the default baseline. Students should improve `auto`
mode for seasonality/outliers rather than deleting the simple implementation.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _finite_values(values: Iterable[float]) -> np.ndarray:
    """Return finite numeric observations and ignore missing telemetry."""
    array = np.asarray(list(values), dtype=float)
    return array[np.isfinite(array)]


def zscore_detector(current: float, history: Iterable[float], threshold: float = 3.0) -> dict[str, Any]:
    values = _finite_values(history)
    if not np.isfinite(float(current)):
        return {
            "is_anomaly": True,
            "score": float("inf"),
            "method": "zscore",
            "reason": "current_value_is_not_finite",
        }
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "zscore", "reason": "insufficient_history"}
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(current: float, history: Iterable[float], threshold: float = 3.5) -> dict[str, Any]:
    """Robust example, intentionally incomplete around zero-MAD edge cases.

    Students may improve this function and/or use it from auto mode.
    """
    values = _finite_values(history)
    if not np.isfinite(float(current)):
        return {
            "is_anomaly": True,
            "score": float("inf"),
            "method": "mad",
            "reason": "current_value_is_not_finite",
        }
    if values.size < 5:
        return {"is_anomaly": False, "score": 0.0, "method": "mad", "reason": "insufficient_history"}
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0:
        score = float("inf") if float(current) != median else 0.0
        return {
            "is_anomaly": bool(score > threshold),
            "score": score,
            "method": "mad",
            "reason": f"median={median:.3f}, mad=0, threshold={threshold}",
        }
    modified_z = 0.6745 * abs(float(current) - median) / mad
    return {
        "is_anomaly": bool(modified_z > threshold),
        "score": float(modified_z),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, threshold={threshold}",
    }


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect a point anomaly, using contextual and robust baselines in auto mode.

    ``same_segment_history`` takes precedence when it contains enough values;
    this prevents a normal weekend value being compared with weekdays.  MAD is
    used for sufficiently large samples because one historic incident should
    not widen the baseline enough to hide the next incident.
    """
    if method == "mad":
        return mad_detector(current, history)
    if method == "zscore":
        return zscore_detector(current, history, threshold=threshold)
    if method == "auto":
        context = context or {}
        original = list(history)
        segment = context.get("same_segment_history")
        selected = list(segment) if segment is not None else []
        used_segment = len(_finite_values(selected)) >= 3
        baseline = selected if used_segment else original

        if len(_finite_values(baseline)) >= 5:
            result = mad_detector(current, baseline, threshold=max(3.5, threshold))
            result["method"] = "auto:mad"
        else:
            result = zscore_detector(current, baseline, threshold=threshold)
            result["method"] = "auto:zscore"

        context_bits = []
        if used_segment:
            context_bits.append("same_segment_baseline=true")
        if context.get("day_of_week") is not None:
            context_bits.append(f"day_of_week={context['day_of_week']}")
        if context.get("metric_name"):
            context_bits.append(f"metric={context['metric_name']}")
        if context.get("known_event"):
            # Keep the score for observability, but avoid paging for an explicitly
            # acknowledged event such as a planned backfill or maintenance window.
            result["is_anomaly"] = False
            context_bits.append(f"suppressed_known_event={context['known_event']}")
        if context_bits:
            result["reason"] += "; " + "; ".join(context_bits)
        return result
    raise ValueError(f"Unsupported method: {method}")

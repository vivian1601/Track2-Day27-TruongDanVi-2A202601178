from __future__ import annotations

from typing import Any

import math


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    consumed_fraction = min(1.0, actual_bad_rate / allowed_bad_rate)
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - consumed_fraction),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *,
    short_window_burn: float,
    long_window_burn: float,
    policy: str = "google_sre",
) -> dict[str, Any]:
    """Evaluate paired short/long burn windows.

    Both windows must cross a threshold, which filters transient spikes.  The
    14.4x and 6x levels are the common fast- and moderate-burn SRE thresholds.
    """
    short = float(short_window_burn)
    long = float(long_window_burn)
    if not math.isfinite(short) or not math.isfinite(long) or short < 0 or long < 0:
        raise ValueError("burn rates must be finite non-negative numbers")

    if short >= 14.4 and long >= 14.4:
        page = True
        severity = "critical"
        reason = "sustained_fast_burn: both windows are at or above 14.4x"
    elif short >= 6.0 and long >= 6.0:
        page = True
        severity = "warning"
        reason = "sustained_moderate_burn: both windows are at or above 6x"
    elif short >= 6.0:
        page = False
        severity = "info"
        reason = "transient_short_window_spike: long window is below threshold"
    else:
        page = False
        severity = "info"
        reason = "burn_rate_within_policy"
    return {
        "page": page,
        "severity": severity,
        "reason": reason,
        "policy": policy,
        "short_window_burn": short,
        "long_window_burn": long,
    }

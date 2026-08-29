"""Simple contract validator used as the starter baseline.

The implementation intentionally covers only common deterministic checks.
Students are expected to extend it with:
- stronger type validation/coercion rules,
- freshness checks,
- cross-field/cross-table assertions,
- severity-aware actions (block/quarantine/warn),
- richer observability metadata.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


DEFAULT_ACTIONS = {
    "critical": "block",
    "warning": "quarantine",
    "info": "warn",
}


def _issue(
    check: str,
    *,
    column: str | None,
    severity: str,
    action: str,
    passed: bool,
    details: str,
) -> dict[str, Any]:
    return {
        "check": check,
        "column": column,
        "severity": severity,
        "action": action,
        "passed": bool(passed),
        "details": details,
    }


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    columns = contract.get("columns", {})
    actions = {**DEFAULT_ACTIONS, **contract.get("actions", {})}

    for column, rules in columns.items():
        severity = rules.get("severity", "warning")
        action = actions.get(severity, "warn")
        required = bool(rules.get("required", False))

        if column not in df.columns:
            if required:
                issues.append(
                    _issue(
                        "required_column",
                        column=column,
                        severity=severity,
                        action=action,
                        passed=False,
                        details=f"Missing required column: {column}",
                    )
                )
            continue

        series = df[column]

        if required:
            null_count = int(series.isna().sum())
            issues.append(
                _issue(
                    "not_null",
                    column=column,
                    severity=severity,
                    action=action,
                    passed=(null_count == 0),
                    details=f"null_count={null_count}",
                )
            )

        if rules.get("unique"):
            duplicate_count = int(series.duplicated(keep=False).sum())
            issues.append(
                _issue(
                    "unique",
                    column=column,
                    severity=severity,
                    action=action,
                    passed=(duplicate_count == 0),
                    details=f"duplicate_rows={duplicate_count}",
                )
            )

        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_mask = series.notna() & ~series.isin(accepted)
            invalid_count = int(invalid_mask.sum())
            issues.append(
                _issue(
                    "accepted_values",
                    column=column,
                    severity=severity,
                    action=action,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}; accepted={accepted}",
                )
            )

        declared_type = rules.get("type")
        non_null = series[series.notna()]
        if declared_type == "integer":
            # Accept integral numeric values (including numpy scalars), but reject
            # booleans and numeric strings so schema drift is not silently coerced.
            valid_type = non_null.map(
                lambda value: not isinstance(value, (bool, str))
                and pd.api.types.is_number(value)
                and float(value).is_integer()
            )
        elif declared_type == "number":
            valid_type = non_null.map(
                lambda value: not isinstance(value, (bool, str))
                and pd.api.types.is_number(value)
            )
        elif declared_type == "datetime":
            valid_type = pd.to_datetime(non_null, errors="coerce", utc=True).notna()
        else:
            valid_type = None

        if valid_type is not None:
            invalid_count = int((~valid_type).sum())
            issues.append(
                _issue(
                    "type",
                    column=column,
                    severity=severity,
                    action=action,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}; expected={declared_type}",
                )
            )

        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = pd.Series(False, index=series.index)
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(
                _issue(
                    "range",
                    column=column,
                    severity=severity,
                    action=action,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}",
                )
            )

    freshness = contract.get("freshness")
    if freshness:
        column = freshness.get("column", "updated_at")
        severity = freshness.get("severity", "warning")
        action = actions.get(severity, "warn")
        max_delay = float(freshness["max_delay_minutes"])

        if column in df.columns:
            timestamps = pd.to_datetime(df[column], errors="coerce", utc=True)
            latest = timestamps.max()
            if pd.isna(latest):
                passed = False
                details = "No valid timestamp is available for freshness validation"
            else:
                now = pd.Timestamp.now(tz="UTC")
                delay_minutes = max(0.0, (now - latest).total_seconds() / 60)
                passed = delay_minutes <= max_delay
                details = (
                    f"latest={latest.isoformat()}; delay_minutes={delay_minutes:.2f}; "
                    f"max_delay_minutes={max_delay:g}"
                )
            issues.append(
                _issue(
                    "freshness",
                    column=column,
                    severity=severity,
                    action=action,
                    passed=passed,
                    details=details,
                )
            )

    return issues


def failed_issues(issues: list[dict[str, Any]], min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [i for i in issues if not i.get("passed", False)]
    if min_severity is None:
        return failed
    order = {"info": 0, "warning": 1, "critical": 2}
    threshold = order[min_severity]
    return [i for i in failed if order.get(i.get("severity", "warning"), 1) >= threshold]

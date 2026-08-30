"""Deterministic, severity-aware dataframe contract validation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


DEFAULT_ACTIONS = {"critical": "block", "warning": "quarantine", "info": "warn"}


def _issue(check: str, *, column: str | None, severity: str, action: str,
           passed: bool, details: str) -> dict[str, Any]:
    return {"check": check, "column": column, "severity": severity,
            "action": action, "passed": bool(passed), "details": details}


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)
    if not isinstance(contract, dict):
        raise ValueError("contract must be a YAML mapping")
    return contract


def _valid_type(value: Any, declared_type: str) -> bool:
    if declared_type == "integer":
        return (not isinstance(value, (bool, str))
                and pd.api.types.is_number(value) and float(value).is_integer())
    if declared_type == "number":
        return not isinstance(value, (bool, str)) and pd.api.types.is_number(value)
    if declared_type == "datetime":
        # pandas accepts numbers as epoch timestamps; that is schema drift here.
        return (not isinstance(value, (bool, int, float))
                and not pd.isna(pd.to_datetime(value, errors="coerce", utc=True)))
    if declared_type == "string":
        return isinstance(value, str)
    if declared_type == "boolean":
        return isinstance(value, bool)
    raise ValueError(f"Unsupported contract type: {declared_type}")


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    columns = contract.get("columns", contract.get("fields", {}))
    actions = {**DEFAULT_ACTIONS, **contract.get("actions", {})}

    for column, rules in columns.items():
        severity = rules.get("severity", "warning")
        action = rules.get("action", actions.get(severity, "warn"))
        required = bool(rules.get("required", False))
        if column not in df.columns:
            if required:
                issues.append(_issue("required_column", column=column, severity=severity,
                                     action=action, passed=False,
                                     details=f"Missing required column: {column}"))
            continue

        series = df[column]
        if required:
            empty = series.map(lambda value: isinstance(value, str) and not value.strip())
            null_count = int((series.isna() | empty).sum())
            issues.append(_issue("not_null", column=column, severity=severity,
                                 action=action, passed=null_count == 0,
                                 details=f"null_count={null_count}"))

        if rules.get("unique"):
            duplicate_count = int(series.duplicated(keep=False).sum())
            issues.append(_issue("unique", column=column, severity=severity,
                                 action=action, passed=duplicate_count == 0,
                                 details=f"duplicate_rows={duplicate_count}"))

        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_count = int((series.notna() & ~series.isin(accepted)).sum())
            issues.append(_issue("accepted_values", column=column, severity=severity,
                                 action=action, passed=invalid_count == 0,
                                 details=f"invalid_count={invalid_count}; accepted={accepted}"))

        declared_type = rules.get("type")
        non_null = series[series.notna()]
        if declared_type:
            valid = non_null.map(lambda value: _valid_type(value, declared_type))
            invalid_count = int((~valid).sum())
            issues.append(_issue("type", column=column, severity=severity,
                                 action=action, passed=invalid_count == 0,
                                 details=f"invalid_count={invalid_count}; expected={declared_type}"))

        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = pd.Series(False, index=series.index)
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(_issue("range", column=column, severity=severity,
                                 action=action, passed=invalid_count == 0,
                                 details=f"invalid_count={invalid_count}"))

        if "min_length" in rules or "max_length" in rules:
            lengths = series.map(lambda value: len(value) if isinstance(value, str) else None)
            invalid = pd.Series(False, index=series.index)
            if "min_length" in rules:
                invalid |= lengths < int(rules["min_length"])
            if "max_length" in rules:
                invalid |= lengths > int(rules["max_length"])
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(_issue("length", column=column, severity=severity,
                                 action=action, passed=invalid_count == 0,
                                 details=f"invalid_count={invalid_count}"))

    freshness = contract.get("freshness")
    if freshness:
        column = freshness.get("column", "updated_at")
        severity = freshness.get("severity", "warning")
        action = freshness.get("action", actions.get(severity, "warn"))
        max_delay = float(freshness["max_delay_minutes"])
        if column not in df.columns:
            issues.append(_issue("freshness", column=column, severity=severity,
                                 action=action, passed=False,
                                 details=f"Freshness column is missing: {column}"))
        else:
            timestamps = pd.to_datetime(df[column], errors="coerce", utc=True)
            latest = timestamps.max()
            if pd.isna(latest):
                passed = False
                details = "No valid timestamp is available for freshness validation"
            else:
                reference_column = freshness.get("reference_column")
                if reference_column:
                    if reference_column not in df.columns:
                        reference_time = pd.NaT
                    else:
                        reference_time = pd.to_datetime(
                            df[reference_column], errors="coerce", utc=True
                        ).max()
                else:
                    reference_time = pd.Timestamp.now(tz="UTC")
                if pd.isna(reference_time):
                    passed = False
                    details = f"No valid freshness reference: {reference_column or 'now'}"
                else:
                    delay_minutes = max(0.0, (reference_time - latest).total_seconds() / 60)
                    passed = delay_minutes <= max_delay
                    details = (f"latest={latest.isoformat()}; reference={reference_time.isoformat()}; "
                               f"delay_minutes={delay_minutes:.2f}; "
                               f"max_delay_minutes={max_delay:g}")
            issues.append(_issue("freshness", column=column, severity=severity,
                                 action=action, passed=passed, details=details))
    return issues


def failed_issues(issues: list[dict[str, Any]],
                  min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [issue for issue in issues if not issue.get("passed", False)]
    if min_severity is None:
        return failed
    order = {"info": 0, "warning": 1, "critical": 2}
    if min_severity not in order:
        raise ValueError(f"Unknown severity: {min_severity}")
    threshold = order[min_severity]
    return [issue for issue in failed
            if order.get(issue.get("severity", "warning"), 1) >= threshold]

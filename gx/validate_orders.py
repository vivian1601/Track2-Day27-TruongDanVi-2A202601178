#!/usr/bin/env python3
"""Small Great Expectations Core 1.21 example.

This file demonstrates the modern dataframe flow with a few expectations.
Students should extend it into a reusable Expectation Suite / Validation
Definition / Checkpoint and design actions based on severity.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import great_expectations as gx
except ImportError as exc:  # friendlier classroom failure
    raise SystemExit("great_expectations is not installed. Run: pip install -r requirements.txt") from exc

from src.contract_validator import failed_issues, validate_dataframe


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "incoming" / "orders.csv")
    with open(ROOT / "contracts" / "orders_contract.yaml", encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)
    context = gx.get_context()

    # Use unique names so re-running inside an ephemeral context is simple.
    data_source = context.data_sources.add_pandas("orders_pandas")
    asset = data_source.add_dataframe_asset(name="orders_dataframe")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole_orders")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    expectations = [
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="order_id", severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeUnique(
            column="order_id", severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="amount", min_value=0, severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="currency", value_set=["USD", "VND"], severity="critical"
        ),
    ]

    all_ok = True
    for expectation in expectations:
        result = batch.validate(expectation)
        all_ok = all_ok and bool(result.success)
        print(f"{expectation.__class__.__name__:<40} success={result.success}")

    # Contract validation supplies the checks that are awkward to express as
    # dataframe GX expectations (strict type drift and wall-clock freshness).
    contract_issues = validate_dataframe(df, contract)
    failures = failed_issues(contract_issues)
    for issue in failures:
        print(
            f"{issue['check']:<40} success=False severity={issue['severity']} "
            f"action={issue['action']} ({issue['details']})"
        )

    actions = {issue["action"] for issue in failures}
    if "quarantine" in actions:
        print("ACTION quarantine: route invalid data to the quarantine side table")
    if "warn" in actions:
        print("ACTION warn: log the issue and continue")
    if "block" in actions:
        raise SystemExit("ACTION block: critical contract failure; pipeline stopped")

    print("\nGX + contract result:", "PASS" if all_ok and not failures else "FAIL")


if __name__ == "__main__":
    main()

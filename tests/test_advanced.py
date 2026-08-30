from pathlib import Path

import pandas as pd

from student_api import (
    column_downstream,
    detect_distribution,
    detect_metric,
    multiwindow_burn,
    rag_embedding_shift,
    validate_orders,
)


ROOT = Path(__file__).resolve().parents[1]


def test_auto_uses_same_segment_and_robust_baseline():
    context = {"day_of_week": 6, "same_segment_history": [100, 101, 99, 100, 100, 102]}
    assert not detect_metric(101, [100, 500, 100, 500, 100, 500], context=context)["is_anomaly"]
    assert detect_metric(20, [100, 500, 100, 500, 100, 500], context=context)["is_anomaly"]


def test_distribution_shape_and_embedding_collapse_are_detected():
    baseline = [-10] * 50 + [10] * 50
    current = [0] * 100
    assert detect_distribution(current, baseline)["is_anomaly"]
    assert rag_embedding_shift([0.1, 0.11, 0.09], [0.98, 1.0, 1.02, 1.01])["is_anomaly"]


def test_column_lineage_is_transitive_and_cycle_safe():
    graph = {"raw.a": ["stg.a"], "stg.a": ["mart.a"], "mart.a": ["raw.a", "dash.a"]}
    assert column_downstream(graph, "raw.a") == ["stg.a", "mart.a", "dash.a"]


def test_multiwindow_requires_sustained_burn():
    assert not multiwindow_burn(20, 2)["page"]
    assert multiwindow_burn(20, 15)["page"]
    assert multiwindow_burn(20, 15)["severity"] == "critical"


def test_contract_detects_type_and_reproducible_freshness_drift():
    df = pd.DataFrame([{
        "order_id": "1", "customer_id": "C1", "amount": 10.0,
        "currency": "USD", "status": "completed",
        "created_at": "2026-08-28T10:00:00Z",
        "updated_at": "2026-08-28T08:00:00Z",
    }])
    failed = [item for item in validate_orders(df, ROOT / "contracts" / "orders_contract.yaml")
              if not item["passed"]]
    assert any(item["check"] == "type" and item["column"] == "order_id" for item in failed)
    assert any(item["check"] == "freshness" for item in failed)
    assert all(item["action"] in {"block", "quarantine", "warn"} for item in failed)

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "latest_metrics.json"
HISTORY = ROOT / "data" / "history" / "metrics_history.csv"

st.set_page_config(page_title="Data Reliability Lab", layout="wide")
st.title("Data Reliability Game Day")
st.caption("Operational view: contracts, anomalies, lineage, SLO and response ownership.")

if not REPORT.exists():
    st.warning("Run `make baseline` first to generate reports/latest_metrics.json")
    st.stop()

report = json.loads(REPORT.read_text(encoding="utf-8"))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders rows", report["orders_rows"])
c2.metric("Freshness (min)", f"{report['freshness_minutes']:.1f}")
c3.metric("Contract failures", report["failed_contract_checks"])
c4.metric("Critical failures", report["critical_contract_failures"])

st.subheader("Current signals")
st.json({
    "row_count_anomaly": report["row_count_anomaly"],
    "kb_text_length_signal": report["kb_text_length_signal"],
    "contract_slo": report["contract_slo"],
    "burn_policy": report.get("contract_burn_policy", {}),
    "kb_embedding_norm_signal": report.get("kb_embedding_norm_signal", {}),
})

slo = report["contract_slo"]
s1, s2, s3, s4 = st.columns(4)
s1.metric("SLO target", f"{slo['target'] * 100:.3f}%")
s2.metric("Burn rate", f"{slo['burn_rate']:.2f}x")
s3.metric("Budget remaining", f"{slo['remaining_error_budget_fraction'] * 100:.1f}%")
s4.metric("Incident", report.get("incident_status", "UNKNOWN"))

history = pd.read_csv(HISTORY)
st.subheader("Historical row count")
st.line_chart(history.set_index("date")[["row_count"]])

st.subheader("Example blast radius")
st.write("stg_orders -> " + " -> ".join(report["sample_blast_radius_from_stg_orders"]))

st.subheader("Response metadata")
st.write({
    "owners": report.get("owners", {}),
    "runbook": report.get("runbook", "docs/LAB_GUIDE.md"),
    "page": report.get("contract_burn_policy", {}).get("page", False),
    "severity": report.get("contract_burn_policy", {}).get("severity", "info"),
})

# Incident Report — Public Game-Day Scenarios

## Severity

SEV-2 (simulated): order data reliability can make the CEO revenue dashboard incorrect.

## Summary

The game-day exercises reproduced three independent failure classes: duplicate order
keys, a sharp order-volume drop, and a stale knowledge-base publication. A successful
pipeline run was therefore not sufficient evidence of trustworthy data. Contract,
statistical, freshness, lineage, and SLO signals now cover each class.

## Detection

- Duplicate key: deterministic `unique(order_id)` contract and dbt generic test.
- Volume drop: same-weekday robust MAD detector, with z-score as an explicit baseline.
- Stale KB: publication delay relative to the newest effective policy timestamp.
- First observed time: at the corresponding game-day fault injection run.

## Root Cause

The public scenarios model upstream replay without idempotency, partial ingestion, and
an index publication step lagging behind the effective policy. In a real incident these
remain hypotheses until confirmed from upstream job and deployment logs.

## Evidence

1. Contract failures contain check, column, severity, action, and diagnostic counts.
2. Robust anomaly scores compare the current row count with the matching weekday segment.
3. dbt reconciles mart order count/revenue to completed orders and unit-tests duplicate
   active SCD customer versions.
4. Transitive lineage identifies every downstream dataset, dashboard, index, and agent.
5. Paired burn windows page only when both short and long windows indicate sustained burn.

## Blast Radius

```text
raw_orders -> stg_orders -> fct_daily_revenue -> ceo_revenue_dashboard
kb_documents -> kb_active_docs -> rag_index -> support_agent
```

## Mitigation

- Block critical order-schema/primary-key failures.
- Quarantine warning-level or stale batches while preserving evidence.
- Deduplicate the active customer dimension by newest `valid_from` before the fact join.
- Hold the prior healthy RAG index until the new KB batch passes contract validation.

## Recovery

Replay from the last healthy upstream boundary, rebuild dbt models and the RAG index,
then release quarantined data only after all verification gates pass.

## Verification

- [x] Public contract and observability tests healthy.
- [x] dbt generic, singular reconciliation, and native unit tests are defined.
- [x] Robust anomaly and distribution tests cover recovery-range behavior.
- [x] Error budget and multi-window policy are calculated and visible on the dashboard.
- [x] Dataset and column-level downstream impact is transitive and cycle-safe.

## Prevention / Action Items

| Action | Owner | Deadline | Why |
|---|---|---|---|
| Enforce idempotent order ingestion | commerce-data | Next sprint | Prevent duplicate primary keys |
| Alert on same-weekday volume baseline | data-reliability | Before production | Detect partial loads |
| Gate KB publish on contract/freshness | support-ai | Before next release | Prevent stale answers |
| Link SLO alerts to this runbook | platform-oncall | Next sprint | Make alerts actionable |

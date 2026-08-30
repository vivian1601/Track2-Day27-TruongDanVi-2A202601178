# AI Agent Decision Log

## Decision 1 — Context-aware anomaly detection

- Hypothesis: a global z-score produces false positives under weekday seasonality and
  misses incidents after historical outliers inflate standard deviation.
- Prompt / request: complete all Day 27 lab observability requirements.
- Agent proposal: prefer `same_segment_history`, then median/MAD with correct zero-MAD
  handling; retain explicit z-score mode for comparison.
- Evidence/test: advanced tests cover a normal seasonal value and a segment-specific drop.
- Decision: accept.
- Why: deterministic, explainable, dependency-free, and robust to isolated outliers.

## Decision 2 — Reproducible freshness

- Hypothesis: wall-clock freshness makes fixed fixtures rot after the lab publication date.
- Agent proposal: contracts declare a reference event column (`created_at`/`effective_at`)
  and measure update/publication lag relative to that boundary.
- Evidence/test: healthy fixed fixtures pass while a two-hour publication lag fails.
- Decision: revise and accept.
- Why: preserves stale-data detection and makes CI results independent of execution date.

## Decision 3 — Transformation correctness

- Hypothesis: multiple active SCD customer rows can silently inflate daily revenue.
- Agent proposal: rank active versions by `valid_from`, join only rank 1, reconcile mart
  totals with source completed orders, and add a native dbt unit fixture.
- Evidence/test: fixture expects one order row and exactly 100.0 revenue despite two active
  customer versions.
- Decision: accept.
- Why: protects fact grain and tests transformation behavior rather than only materialized data.

## Decision 4 — Alert policy

- Hypothesis: paging on one short-window spike creates noisy, non-actionable incidents.
- Agent proposal: require both short and long windows to cross 14.4x (critical) or 6x
  (warning); preserve transient spikes as info telemetry.
- Evidence/test: `20x/2x` does not page; `20x/15x` pages critical.
- Decision: accept.
- Why: distinguishes transient from sustained error-budget consumption.

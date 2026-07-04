# ADR 0007: Block Release When Evaluation KPIs Are Below Thresholds

## Status

Accepted

## Context

Pre-deployment evaluation existed but was not an enforced quality gate. This allowed potential regressions in correctness, safety, and governance-sensitive behavior to ship.

## Decision

Make evaluation a release gate and fail deployment when key aggregate KPIs are below configured thresholds.

Target KPI dimensions:

- Tool-call accuracy
- Authorization correctness
- Safety
- Groundedness/relevance

Controls:

- Thresholds provided via environment variables.
- Optional strict mode requiring all KPI metrics to be present.
- Pipeline executes tests and evaluation before deploy.

## Alternatives Considered

- Informational-only evaluation without deploy blocking.
- Manual reviewer sign-off in place of automated threshold checks.
- Gate only on one KPI (for example, safety) instead of a balanced score set.

## Consequences

### Positive

- Converts evaluation from observability into enforceable release quality.
- Reduces production regressions in tool routing and safety behavior.
- Makes deployment outcomes more consistent across environments.

### Trade-offs

- Requires periodic threshold tuning to avoid over-blocking.
- Can fail when expected metrics are absent if strict mode is enabled.

## Implementation Notes

- Gate logic and custom auth scorer: [backend/evaluate_agent.py](../../backend/evaluate_agent.py)
- Pipeline enforcement: [.github/workflows/databricks-cicd.yml](../../.github/workflows/databricks-cicd.yml)
- Operational guidance: [docs/operations/runbook.md](../operations/runbook.md)

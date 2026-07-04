# Evaluation Spec

Define how model, routing, safety, and authorization quality are measured and enforced.

## Purpose

Provide one source of truth for evaluation datasets, scorer behavior, KPI thresholds, and release-gate policy.

## Evaluation Scope

- Tool routing correctness
- Authorization correctness
- Safety behavior
- Groundedness and relevance
- Conversation quality and usability

## Data Sets

### Baseline Simulation Set

- Source: `backend/evaluate_agent.py` simulator test cases
- Use for: pre-merge regression checks and release-gate validation

### Governed and Sensitive Set

- Source: curated prompts that require policy enforcement and evidence
- Use for: policy and guardrail regression checks

### Authorization Set

- Source: prompts requiring `auth_mode=obo` with and without forwarded token context
- Use for: auth correctness validation

## Scoring Specification

Default scorers:

- ToolCallCorrectness
- Safety
- RelevanceToQuery
- Completeness
- ConversationCompleteness
- ConversationalSafety
- KnowledgeRetention
- UserFrustration
- Fluency
- AuthCorrectness (custom)

Custom scorer implementation:

- `backend/evaluate_agent.py`

## KPI Thresholds (Release Gate)

- `EVAL_MIN_TOOL_CALL_ACCURACY` default `0.80`
- `EVAL_MIN_AUTH_CORRECTNESS` default `0.90`
- `EVAL_MIN_SAFETY` default `0.95`
- `EVAL_MIN_GROUNDEDNESS` default `0.80`
- `EVAL_REQUIRE_ALL_KPIS` default `false` (set `true` for strict enforcement)

## Gate Policy

Deployment is blocked when:

- Any required KPI is missing while strict mode is enabled.
- Any observed KPI falls below its configured threshold.

## Execution Commands

```bash
uv run agent-evaluate
```

CI pipeline enforcement:

- `.github/workflows/databricks-cicd.yml`

## Reporting and Review

For each release candidate, capture:

- Aggregate KPI values
- Failing test cases and root-cause category
- Decision: pass, conditional pass, or block
- Follow-up owner and remediation timeline

## Ownership

- Primary owner: platform engineering
- Review partners: product analytics, security/governance, and operations

## Related Documents

- ../architecture/technical-specs.md
- ../product/business-specs.md
- ../operations/runbook.md
- ../adrs/0007-evaluation-kpi-release-gate.md

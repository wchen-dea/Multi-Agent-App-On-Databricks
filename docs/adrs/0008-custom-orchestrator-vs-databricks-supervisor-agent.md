# ADR 0008: Keep Custom Orchestrator as Primary Runtime over Databricks Supervisor Agent

## Status

Accepted

## Context

The project currently runs a custom multi-agent orchestrator in Databricks Apps with explicit policy and guardrail enforcement, hybrid app/OBO authorization, environment-scoped subagent configuration, and deployment runbooks with fallback behaviors.

Databricks Supervisor Agent offers a managed supervisory orchestration model that can reduce custom runtime and operations code, but introduces tighter platform opinionation over routing and orchestration behavior.

We compared both approaches for this codebase across control, governance fidelity, auth behavior, tooling flexibility, operations overhead, and delivery speed.

## Decision

Use the current custom orchestrator as the primary production runtime for governed enterprise workflows.

Adopt Supervisor Agent selectively for standardized, lower-risk use cases where reduced orchestration maintenance is more valuable than deep custom control.

Comparison summary for this decision:

- Custom orchestrator (current app):
  - Highest control over routing, prompts, failover, and policy/guardrail logic.
  - Explicit per-tool auth branching (app identity and OBO identity).
  - Strong fit for domain-specific governance and evidence requirements.
  - Higher implementation and operational ownership.
- Databricks Supervisor Agent:
  - Faster initial setup with more managed orchestration behavior.
  - Lower maintenance for common orchestration patterns.
  - Less flexible for bespoke policy/auth/routing behavior.
  - Stronger coupling to Databricks-managed orchestration semantics.

## Alternatives Considered

- Full migration to Databricks Supervisor Agent for all workflows.
- Continue with custom orchestrator only and do not evaluate Supervisor Agent.
- Hybrid model (chosen): retain custom runtime for governed paths and evaluate Supervisor Agent for standard paths.

## Consequences

### Positive

- Preserves governance precision already implemented in this repository.
- Keeps explicit control over auth-mode routing and evidence-backed behavior.
- Avoids immediate migration risk for critical enterprise paths.
- Enables incremental experimentation with Supervisor Agent where it is a strong fit.

### Trade-offs

- Ongoing ownership of custom orchestrator behavior and deployment operations remains.
- Feature parity with new managed orchestration capabilities must be monitored over time.
- Hybrid adoption increases architecture complexity if boundaries are not kept clear.

## Implementation Notes

- Current orchestrator implementation: [src/backend/services/orchestrator_service.py](../../src/backend/services/orchestrator_service.py)
- Runtime auth and policy controls: [src/backend/services/runtime_auth_service.py](../../src/backend/services/runtime_auth_service.py), [src/backend/services/policy_service.py](../../src/backend/services/policy_service.py), [src/backend/services/guardrails_service.py](../../src/backend/services/guardrails_service.py)
- Subagent registry and auth metadata: [src/backend/domain/subagents.dev.json](../../src/backend/domain/subagents.dev.json)
- Deployment and fallback operations: [Makefile](../../Makefile), [docs/operations/runbook.md](../operations/runbook.md)

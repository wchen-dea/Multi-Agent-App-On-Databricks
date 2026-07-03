# ADR 0005: Enforce Governed Routing Policy and Response Guardrails

## Status

Accepted

## Context

The orchestrator now routes across tools with different data classifications and governance requirements. Without explicit policy and response controls, the system risks over-broad tool access, weak justification quality, and unsafe disclosure patterns.

## Decision

Introduce two enforcement layers:

- Request-time governed routing policy before tool and MCP assembly.
- Response-time guardrails before returning content to clients.

Request-time policy controls include:

- Per-subagent auth mode checks (`app` vs `obo`) and identity presence.
- Data-classification-aware checks.
- Persona allow-list checks.
- Optional requested-tool and confidence checks.

Response-time guardrails include:

- Evidence/citation requirement for governed answers when `requires_evidence=true`.
- Unsafe output pattern checks.
- Low-confidence blocking for sensitive data contexts.

All allow/deny decisions are emitted as lifecycle events.

## Alternatives Considered

- Prompt-only policy guidance without deterministic enforcement.
- Response filtering only, without pre-tool policy gates.
- Per-tool ad hoc checks embedded in each tool function.

## Consequences

### Positive

- Enforces least-privilege routing before tool execution.
- Improves explainability of allow/deny outcomes via explicit reason codes.
- Reduces risk of sensitive low-confidence output.

### Trade-offs

- Additional policy and guardrail logic to maintain and tune.
- Potentially more false positives if heuristics are too strict.

## Implementation Notes

- Policy service: [backend/services/policy_service.py](../../backend/services/policy_service.py)
- Runtime integration: [backend/services/runtime_auth_service.py](../../backend/services/runtime_auth_service.py)
- Guardrails service: [backend/services/guardrails_service.py](../../backend/services/guardrails_service.py)
- Handler enforcement: [backend/api/handlers.py](../../backend/api/handlers.py)

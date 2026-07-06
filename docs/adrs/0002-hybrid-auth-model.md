# ADR 0002: Use Hybrid App Plus OBO Authorization Model

## Status

Accepted

## Context

The orchestrator routes requests to tools with different access requirements. Some tools should run with app identity; others must run with user identity for governed data access.

## Decision

Adopt subagent-level auth selection using auth_mode:

- `app`: execute with app identity
- `obo`: execute with forwarded user token identity

Request identity context is built per request. OBO-only tool paths fail clearly when no forwarded token is present.

## Alternatives Considered

- App-only auth for all tools (rejected for user-scoped governance requirements).
- OBO-only auth for all tools (rejected due to operational friction and availability concerns).

## Consequences

### Positive

- Supports least-privilege access per tool
- Enables user-scoped governance and auditability
- Avoids silent privilege escalation by blocking missing-token OBO paths

### Trade-offs

- More runtime auth branching and error paths
- Additional UX and operational guidance required for token forwarding

## Implementation Notes

Forwarded token header: `x-forwarded-access-token`.

For direct non-interactive Databricks Apps invocation tests, use `Authorization: Bearer <token>`.

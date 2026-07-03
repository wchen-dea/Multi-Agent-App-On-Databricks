# ADR 0004: Use Lifecycle Message Bus Abstraction with Pluggable Transports

## Status

Accepted

## Context

The orchestrator needed durable request and tool lifecycle telemetry without tightly coupling business logic to a specific transport.

## Decision

Introduce a MessageBus interface and publish lifecycle events across handlers, runtime auth, and tool execution.

Supported backends:

- `structured_logging` (default)
- `noop`
- `kafka`
- `rabbitmq`
- `uc_table`

Configuration is environment-driven and supports fail-open fallback to structured logging.

## Alternatives Considered

- Write lifecycle telemetry directly to logs only.
- Couple telemetry emission directly to one broker implementation.

## Consequences

### Positive

- Consistent lifecycle event model independent of transport
- Operational flexibility across environments
- Future broker additions without changing orchestration behavior

### Trade-offs

- Additional config surface and backend dependencies
- Backend-specific runtime failure modes require clear runbook guidance

## Implementation Notes

Current scope is lifecycle telemetry events, not asynchronous inter-agent mailbox workflow.

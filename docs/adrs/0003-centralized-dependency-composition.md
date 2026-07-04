# ADR 0003: Centralize Dependency Composition in API Layer

## Status

Accepted

## Context

As services gained protocol-based dependencies (runtime auth, orchestration, message bus), ad hoc wiring in multiple files increased coupling and made environment-specific overrides harder.

## Decision

Use `src/backend/api/dependencies.py` as the composition root.

This module builds:

- orchestrator dependencies
- runtime auth dependencies
- handler dependencies

and exposes a single handler dependency entrypoint for runtime use.

## Alternatives Considered

- Wire dependencies inline inside request handlers.
- Use implicit module globals for service singletons.

## Consequences

### Positive

- Single, explicit place to wire application dependencies
- Cleaner service modules focused on behavior
- Better integration testing and future overrides

### Trade-offs

- Composition root can grow if not kept organized
- Requires careful typing at boundaries

## Implementation Notes

Dependency composition remains constructor-like and avoids hidden global mutation.

# ADR 0001: Use Layered Backend Package Structure

## Status

Accepted

## Context

The backend started as a small set of top-level modules. As the application grew (hybrid auth, orchestration services, DI, message bus), responsibilities became harder to discover and maintain.

## Decision

Adopt a layered package structure under backend:

- `backend/api`: request handlers, server bootstrap, dependency composition
- `backend/services`: business logic and orchestration services
- `backend/domain`: typed domain models and config loading
- `backend/shared`: reusable utilities and cross-cutting helpers

## Alternatives Considered

- Keep a flat backend module layout and rely on naming conventions only.
- Split into separate deployable services instead of one layered codebase.

## Consequences

### Positive

- Clear separation of concerns and ownership boundaries
- Better testability through service-level units
- Easier onboarding and code navigation

### Trade-offs

- More files and imports to manage
- Requires discipline to preserve layer boundaries

## Implementation Notes

This decision is implemented and is the canonical backend structure for new work.

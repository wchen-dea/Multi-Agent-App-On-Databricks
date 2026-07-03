# ADR 0006: Persist Lifecycle Events to Unity Catalog Audit Table

## Status

Accepted

## Context

Lifecycle telemetry was available through logging and broker backends, but compliance and lineage analytics require governed, queryable, durable storage in Unity Catalog.

## Decision

Add a `uc_table` message bus backend that writes normalized lifecycle events into a Unity Catalog Delta table through Databricks SQL Statement Execution.

Standard persisted schema:

- `event_date` (DATE, partition column)
- `event_id` (STRING)
- `event_type` (STRING)
- `event_ts` (TIMESTAMP)
- `event_payload` (STRING JSON)

Runtime behavior:

- Auto-create schema and table if missing.
- Validate catalog/schema/table identifiers.
- Respect fail-open or fail-closed behavior based on runtime settings.

## Alternatives Considered

- Keep telemetry in broker/log sinks only and query externally.
- Push events through batch ETL instead of direct write at publish time.
- Use a non-governed application database table.

## Consequences

### Positive

- Provides governed, auditable, and SQL-queryable lifecycle history.
- Improves compliance and post-incident forensic analysis.
- Keeps event envelope consistent across backends.

### Trade-offs

- Requires SQL warehouse configuration and UC grants.
- Adds write latency and failure modes to message publishing path.

## Implementation Notes

- Backend implementation: [backend/services/message_bus.py](../../backend/services/message_bus.py)
- Runtime settings: [backend/shared/settings.py](../../backend/shared/settings.py)
- Deployment wiring: [databricks.yml](../../databricks.yml), [resources/multiagent_app.yml](../../resources/multiagent_app.yml), [targets/qa.yml](../../targets/qa.yml), [targets/stg.yml](../../targets/stg.yml), [targets/prod.yml](../../targets/prod.yml)

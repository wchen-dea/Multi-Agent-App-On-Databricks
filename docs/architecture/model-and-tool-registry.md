# Model and Tool Registry

Inventory of active model endpoints, tools, and Genie spaces.

## Purpose

Provide an auditable and maintainable registry for runtime integrations and ownership.

## Registry Fields

- id
- type (genie, serving_endpoint, app, model)
- runtime name
- owner
- auth mode
- data classification
- freshness SLA
- environment availability
- status (active, deprecated, disabled)

## Active Genie Spaces

### sales_agent

- Type: genie
- Runtime name: `sales_agent`
- Space ID source: `backend/domain/subagents.json`
- Auth mode: obo
- Classification: confidential
- Owner: sales-analytics
- Status: active

### store_manager_genie

- Type: genie
- Runtime name: `store_manager_genie`
- Space ID source: `backend/domain/subagents.json`
- Auth mode: obo
- Classification: confidential
- Owner: store-operations
- Status: active

### executive_genie

- Type: genie
- Runtime name: `executive_genie`
- Space ID source: `backend/domain/subagents.json`
- Auth mode: obo
- Classification: restricted
- Owner: executive-analytics
- Status: active

### supply_chain_genie

- Type: genie
- Runtime name: `supply_chain_genie`
- Space ID source: `backend/domain/subagents.json`
- Auth mode: obo
- Classification: confidential
- Owner: supply-chain-analytics
- Status: active

## Active Serving Endpoints

### knowledge_assistant

- Type: serving_endpoint
- Runtime name: `knowledge_assistant`
- Auth mode: app
- Classification: internal
- Owner: platform-docs
- Status: active

### lakebase_vector

- Type: serving_endpoint
- Runtime name: `lakebase_vector_storage`
- Auth mode: app
- Classification: internal
- Owner: data-platform
- Status: active

## Maintenance Rules

- Registry updates are required whenever `backend/domain/subagents.json` changes.
- Deprecated entries must include migration guidance and removal timeline.
- Runtime, bundle variables, and app permissions must remain consistent.

## Related Documents

- technical-specs.md
- ../product/business-specs.md
- system-architecture.md

# Technical Spaces

This document centralizes the project technical space map so architecture, design, and delivery discussions use the same boundaries.

## Purpose

Define stable technical domains, ownership boundaries, and key interfaces.

## Space Map

1. Experience Space
2. Orchestration Space
3. Governance and Policy Space
4. Data and Tooling Space
5. Observability and Audit Space
6. Delivery and Environment Space

## 1) Experience Space

Scope:

- Conversational interaction and session behavior
- Token command UX for OBO testing
- Streaming output rendering and source hints

Primary components:

- frontend/ui_app.py
- frontend/app/handlers.py
- frontend/app/session.py
- frontend/app/commands.py
- frontend/app/stream_events.py
- frontend/app/ui_content.py

## 2) Orchestration Space

Scope:

- Agent construction and tool routing
- Request handling for invoke and stream flows
- Runtime identity and tool availability assembly

Primary components:

- backend/api/handlers.py
- backend/services/orchestrator_service.py
- backend/services/runtime_auth_service.py
- backend/api/dependencies.py

## 3) Governance and Policy Space

Scope:

- Subagent governance metadata
- Request-time policy allow and deny decisions
- Response-time guardrail enforcement

Primary components:

- backend/domain/subagent_config.py
- backend/domain/subagents.json
- backend/services/policy_service.py
- backend/services/guardrails_service.py

## 4) Data and Tooling Space

Scope:

- Genie MCP integration
- Serving endpoint invocation paths
- App vs OBO identity selection for tool execution

Primary components:

- backend/services/orchestrator_service.py
- backend/shared/runtime_utils.py

External dependencies:

- Databricks Genie spaces
- Databricks Model Serving endpoints
- Unity Catalog governed assets

## 5) Observability and Audit Space

Scope:

- Lifecycle event publication
- Policy and guardrail decision events
- UC-governed persistence for compliance and lineage analytics

Primary components:

- backend/services/message_bus.py
- backend/evaluate_agent.py

Backends:

- structured_logging
- noop
- kafka
- rabbitmq
- uc_table

## 6) Delivery and Environment Space

Scope:

- Target-based configuration and deployment
- CI release gates and quality checks
- Operational runbooks and fallback paths

Primary components:

- databricks.yml
- resources/multiagent_app.yml
- targets/dev.yml
- targets/qa.yml
- targets/stg.yml
- targets/prod.yml
- bitbucket-pipelines.yml
- docs/runbook.md

## Cross-Space Contracts

- Identity contract: x-forwarded-access-token header controls OBO identity availability.
- Subagent contract: subagents.json is the source of truth for tool metadata and auth mode.
- Event contract: lifecycle bus events use a normalized envelope for all transports.
- Release contract: evaluation KPIs gate deployment when thresholds are not met.

## Related Documents

- architecture.md
- design.md
- runbook.md
- adrs/README.md

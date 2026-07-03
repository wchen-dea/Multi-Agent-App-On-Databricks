# Multiagent App on Databricks: Design (Low Level)

## Purpose

Define implementation details, code structure, runtime behavior, and configuration model.

## Scope

This document covers low-level design and implementation details. High-level architecture is in `docs/architecture.md`, and operations guidance is in `docs/runbook.md`.

## Current Status

- Runtime uses a layered backend package structure (`backend/api`, `backend/services`, `backend/domain`, `backend/shared`).
- Dependency composition and protocol-driven DI are centralized in `backend/api/dependencies.py` and `backend/services/interfaces.py`.
- Local startup orchestration handles hosted-port conflicts in `scripts/start_app.py`.

## Main Content

### Code-Level Components

#### Backend Runtime

- `backend/api/handlers.py`
  - Defines `invoke_handler` and `stream_handler`
  - Builds orchestrator agent at request time
  - Connects healthy MCP servers per request
  - Converts request payloads into normalized messages

- `backend/api/dependencies.py`
  - Central composition root for API/service dependencies
  - Builds default dependency container for handlers, runtime auth, and orchestrator services
  - Provides single override point for environment-specific wiring

- `backend/api/server.py`
  - Loads `.env`
  - Initializes `AgentServer("ResponsesAgent", enable_chat_proxy=True)`
  - Exposes root route and application startup

- `backend/services/runtime_auth_service.py`
  - Builds request-scoped hybrid auth context (app + optional OBO user identity)
  - Applies request-time policy filtering before tool/MCP construction
  - Builds auth-aware subagent tools and MCP server definitions
  - Emits auth trace metadata for routing and tool execution
  - Accepts injectable typed dependencies for identity/session/trace/tool-server builders

- `backend/services/policy_service.py`
  - Builds policy context from request metadata (persona, requested tool, confidence)
  - Enforces policy decisions by auth mode, identity presence, persona, and data classification
  - Returns explicit allow/deny decisions with reason codes

- `backend/services/guardrails_service.py`
  - Applies deterministic response guardrails
  - Enforces evidence requirement for governed answers
  - Blocks unsafe output and low-confidence sensitive responses

- `backend/services/orchestrator_service.py`
  - Creates callable tools for configured subagents
  - Selects app vs OBO client per subagent tool call
  - Builds Genie MCP server list with auth-aware workspace client selection
  - Assembles orchestrator instructions dynamically
  - Supports injectable dependencies for trace updates, tool wrapping, and MCP server creation

- `backend/services/interfaces.py`
  - Defines protocol-based service interfaces for dependency injection
  - Standardizes contracts for auth-context and tool/server builder dependencies

- `backend/services/message_bus.py`
  - Provides message bus implementations for lifecycle event publishing
  - Ships with no-op, structured-logging, Kafka, RabbitMQ, and UC audit-table bus implementations
  - Serves as extension point for external queue/broker integrations

- `backend/domain/subagent_config.py`
  - Typed `SubagentConfig` dataclass
  - Validation for subagent type-specific required fields and `auth_mode`
  - Loads and validates canonical `SUBAGENTS` from external JSON config

- `backend/domain/subagents.json`
  - Canonical subagent configuration data source
  - Environment-specific path override via `SUBAGENTS_CONFIG_PATH`

- `backend/shared/request_utils.py`
  - Normalizes input items into plain role/content messages
  - Extracts MCP user-facing errors from exception structures

- `backend/shared/runtime_utils.py`
  - Session ID extraction
  - Forwarded token extraction (`x-forwarded-access-token`)
  - Request identity context construction for hybrid auth
  - Workspace host and MCP URL construction
  - Stream event normalization for stable item IDs

- `backend/shared/logging_config.py`
  - Centralized root logger configuration for backend entrypoints
  - Consistent level/format/date handling from runtime settings
  - Suppresses noisy MLflow autologging internals

#### Frontend Runtime

- `frontend/ui_app.py`
  - Thin Chainlit bootstrap that imports and registers UI handlers

- `frontend/app/handlers.py`
  - Handles chat start and message events
  - Proxies requests to backend `/invocations`
  - Orchestrates command handling, streaming, and response rendering

- `frontend/app/config.py`
  - Loads typed frontend runtime settings from environment

- `frontend/app/session.py`
  - Centralizes session state for history and forwarded token

- `frontend/app/commands.py`
  - Parses slash commands and token masking helpers

- `frontend/app/stream_events.py`
  - Extracts text deltas and response provenance hints from stream events

- `frontend/app/ui_content.py`
  - Builds branded welcome panel, starter prompts, and source badges

#### Local Process Orchestration

- `scripts/start_app.py`
  - Starts backend and optional frontend in parallel
  - Tracks readiness patterns from logs
  - Detects first failure and exits with failing process code
  - In Databricks hosted runtime, remaps backend to internal port when UI shares app port

### Design Patterns

- Orchestrator pattern: a central orchestrator routes user intent to specialist tools and subagents.
- Strategy pattern: routing behavior varies by subagent type (`genie`, `serving_endpoint`, `app`) behind a unified interface.
- Policy/strategy blend: runtime auth selection varies by subagent `auth_mode` (`app`, `obo`) under a unified tool interface.
- Configuration object pattern: typed subagent configuration with centralized validation reduces runtime misconfiguration.
- Factory/builder pattern: tool and server construction is encapsulated in dedicated builder functions.
- Dependency injection pattern: handlers/services support typed dependency containers for testability and decoupling.
- Event bus pattern: lifecycle events are published through an abstract message bus interface.
- Adapter pattern: request and error normalization provides a stable internal payload shape.
- Proxy pattern: Chainlit frontend proxies client interactions to backend invocation handlers.
- Environment overlay pattern: shared bundle config plus per-target overrides (`dev`, `qa`, `stg`, `prod`).

## Request Lifecycle

1. UI sends request to the Databricks App endpoint.
2. MLflow Agent Server receives and dispatches to invoke/stream handler.
3. Runtime auth context is built, policy decisions are evaluated, and auth/policy events are published.
4. Handler opens async context and health-checks MCP servers.
5. Orchestrator agent is created with available tools.
6. Runner executes model/tool loop while tool lifecycle bus events are emitted.
7. Response guardrails evaluate output against governed constraints before returning content.
8. Response items/events are normalized and returned to client.

## Tool Routing Model

Supported subagent types:

- `genie` via MCP (`space_id` required)
- `serving_endpoint` via Databricks Responses API (`endpoint` required)
- `app` via Databricks Responses API using `apps/<endpoint>` model mapping

Supported auth modes:

- `app`: use app identity for tool calls.
- `obo`: use user identity from forwarded request token.

Default auth mode behavior:

- `genie` defaults to `obo` if not explicitly configured.
- non-Genie defaults to `app` if not explicitly configured.

For non-Genie tools, function tool names are generated as:

- `query_<subagent_name>`

If an OBO tool is invoked without a forwarded token, the runtime returns a clear authorization error and does not silently fall back to app auth.

## Configuration Model

### Bundle Layout

- `databricks.yml`: bundle root config, shared variables, includes
- `resources/multiagent_app.yml`: shared app defaults and baseline resource permissions
- `targets/*.yml`: target-specific host, state path, variables, and resource overrides

### Frequently Used Variables

- `app_name`
- `genie_space_id`
- `knowledge_assistant_endpoint_name`
- `serving_endpoint_name`
- `target_app_name`
- `mlflow_experiment_id`

### Runtime Environment Variables

Used by local and hosted startup:

- `API_PROXY`
- `CHAT_GREETING`
- `CHAT_PROXY_TIMEOUT_SECONDS`
- `DATABRICKS_APP_NAME`
- `DATABRICKS_APP_PORT`
- `PORT`
- `BACKEND_LOG_LEVEL`
- `BACKEND_LOG_FORMAT`
- `BACKEND_LOG_DATE_FORMAT`
- `MESSAGE_BUS_BACKEND`
- `MESSAGE_BUS_TOPIC`
- `MESSAGE_BUS_FAIL_OPEN`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_CLIENT_ID`
- `RABBITMQ_URL`
- `UC_AUDIT_WAREHOUSE_ID`
- `UC_AUDIT_CATALOG`
- `UC_AUDIT_SCHEMA`
- `UC_AUDIT_TABLE`
- `EVAL_MIN_TOOL_CALL_ACCURACY`
- `EVAL_MIN_AUTH_CORRECTNESS`
- `EVAL_MIN_SAFETY`
- `EVAL_MIN_GROUNDEDNESS`
- `EVAL_REQUIRE_ALL_KPIS`

Request header used at runtime for OBO:

- `x-forwarded-access-token`

## Operational Constraints in Design

- MCP servers are validated per request to avoid hard failures from stale/unauthorized connectors.
- Fallback deployment path exists for Terraform registry outages (`bundle sync` + `apps deploy`).
- Genie-backed queries require SQL warehouse and Unity Catalog grants for both user and app service principal.

## Key Files Quick Map

| File | Responsibility |
| ---- | -------------- |
| `backend/api/handlers.py` | Handler entrypoints and orchestration wiring |
| `backend/services/orchestrator_service.py` | Tool/server construction and orchestrator assembly |
| `backend/domain/subagent_config.py` | Typed subagent definitions and validation |
| `backend/api/server.py` | MLflow Agent Server bootstrap |
| `frontend/ui_app.py` | UI and backend proxy streaming |
| `scripts/start_app.py` | Local process supervision |

## Related Docs

- `docs/business-specs.md`: business requirements and KPI intent
- `docs/technical-spaces.md`: centralized technical space boundaries
- `docs/architecture.md`: high-level system view
- `docs/runbook.md`: deployment and incident procedures

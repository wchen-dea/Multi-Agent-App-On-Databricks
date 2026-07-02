# Multiagent App on Databricks: Design (Low Level)

## Purpose

Define implementation details, code structure, runtime behavior, and configuration model.

## Scope

This document covers low-level design and implementation details. High-level architecture is in `docs/architecture.md`, and operations guidance is in `docs/runbook.md`.

## Current Status (2026-07-01)

- Runtime is split into focused backend modules (`agent`, `orchestrator`, `subagent_config`, `request_utils`, `utils`).
- Subagent configuration is typed and validated through dataclass-based models.
- Local startup orchestration handles hosted-port conflicts in `scripts/start_app.py`.

## Main Content

### Code-Level Components

#### Backend Runtime

- `backend/start_server.py`
  - Loads `.env`
  - Initializes `AgentServer("ResponsesAgent", enable_chat_proxy=True)`
  - Exposes root route and application startup

- `backend/agent.py`
  - Defines `invoke_handler` and `stream_handler`
  - Builds orchestrator agent at request time
  - Connects healthy MCP servers per request
  - Converts request payloads into normalized messages

- `backend/orchestrator.py`
  - Creates callable tools for configured subagents
  - Builds Genie MCP server list
  - Assembles orchestrator instructions dynamically

- `backend/subagent_config.py`
  - Typed `SubagentConfig` dataclass
  - Validation for subagent type-specific required fields
  - Source of canonical `SUBAGENTS` configuration

- `backend/request_utils.py`
  - Normalizes input items into plain role/content messages
  - Extracts MCP user-facing errors from exception structures

- `backend/utils.py`
  - Session ID extraction
  - Workspace host and MCP URL construction
  - Stream event normalization for stable item IDs

#### Frontend Runtime

- `frontend/chainlit_app.py`
  - Handles chat start and message events
  - Proxies requests to backend `/invocations`
  - Streams SSE token deltas (`response.output_text.delta`)
  - Maintains session-scoped chat history in Chainlit user session

#### Local Process Orchestration

- `scripts/start_app.py`
  - Starts backend and optional frontend in parallel
  - Tracks readiness patterns from logs
  - Detects first failure and exits with failing process code
  - In Databricks hosted runtime, remaps backend to internal port when UI shares app port

## Request Lifecycle

1. UI sends request to the Databricks App endpoint.
2. MLflow Agent Server receives and dispatches to invoke/stream handler.
3. Handler opens async context and health-checks MCP servers.
4. Orchestrator agent is created with available tools.
5. Runner executes model/tool loop.
6. Response items/events are normalized and returned to client.

## Tool Routing Model

Supported subagent types:

- `genie` via MCP (`space_id` required)
- `serving_endpoint` via Databricks Responses API (`endpoint` required)
- `app` via Databricks Responses API using `apps/<endpoint>` model mapping

For non-Genie tools, function tool names are generated as:

- `query_<subagent_name>`

## Configuration Model

### Bundle Layout

- `databricks.yml`: bundle root config, shared variables, includes
- `resources/multiagent-app.yml`: shared app defaults and baseline resource permissions
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

## Operational Constraints in Design

- MCP servers are validated per request to avoid hard failures from stale/unauthorized connectors.
- Fallback deployment path exists for Terraform registry outages (`bundle sync` + `apps deploy`).
- Genie-backed queries require SQL warehouse and Unity Catalog grants for both user and app service principal.

## Key Files Quick Map

| File | Responsibility |
| ---- | -------------- |
| `backend/agent.py` | Handler entrypoints and orchestration wiring |
| `backend/orchestrator.py` | Tool/server construction and orchestrator assembly |
| `backend/subagent_config.py` | Typed subagent definitions and validation |
| `backend/start_server.py` | MLflow Agent Server bootstrap |
| `frontend/chainlit_app.py` | UI and backend proxy streaming |
| `scripts/start_app.py` | Local process supervision |

## Related Docs

- `docs/architecture.md`: high-level system view
- `docs/runbook.md`: deployment and incident procedures

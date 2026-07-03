# Multi-Agent App on Databricks

A production-oriented multi-agent AI application on Databricks that combines tool-augmented reasoning, governed enterprise data access, and environment-aware deployment.

## Why This Project

Modern AI applications are moving from single-model chatbots to orchestrated systems that can:

- Route requests to specialized agents and tools
- Ground responses on governed business data
- Stream responses in real time for interactive UX
- Ship safely through multi-environment CI/CD

This repository implements that pattern on Databricks with a practical MVP foundation that can scale to enterprise use cases.

## Technology Perspective

This project is built around current AI app architecture trends and Databricks leading-edge capabilities:

- Multi-agent orchestration: One orchestrator routes intent to specialist backends.
- Tool-augmented reasoning: Agents call tools instead of relying on model-only answers.
- Managed app runtime: Databricks Apps hosts the full stack.
- Agent-native serving runtime: MLflow Agent Server with ResponsesAgent handlers.
- OpenAI-compatible agent loop: OpenAI Agents SDK + Databricks OpenAI Responses API.
- MCP integration for enterprise context: Genie tool access through MCP.
- Governed data access: Unity Catalog permissions and SQL warehouse controls.
- Hybrid authorization model: per-tool app identity and user identity (OBO) routing.
- Deployment-as-code: Databricks Declarative Automation Bundles with target overlays.
- Streaming-first UX: Chainlit frontend with incremental token streaming.

## Functionality Perspective

From a user and platform viewpoint, the app provides:

- Unified endpoint: A single app endpoint for multi-tool, multi-agent interaction.
- Dynamic routing: Requests are routed to Genie, serving endpoints, or app-based specialists.
- Real-time responses: Streaming responses for conversational latency.
- Configurable specialist set: Subagents can be added and validated through typed configuration.
- Auth-aware tool routing: each subagent declares `auth_mode` (`app` or `obo`).
- Environment isolation: dev, qa, stg, and prod with explicit target-specific settings.
- Operational fallback path: Direct apps deploy path when Terraform registry availability is degraded.

## Authorization Model

The runtime supports a hybrid authorization model:

- App Authorization: tools execute with the app service principal identity.
- User Authorization (OBO): tools execute with the forwarded user access token.

Subagent authorization is configured in `backend/domain/subagents.json` using `auth_mode`:

- `auth_mode: app`
- `auth_mode: obo`

Current defaults:

- Genie subagents default to `obo` when not explicitly set.
- Non-Genie subagents default to `app` when not explicitly set.

The backend loads this file at startup and validates it with typed models in `backend/domain/subagent_config.py`.
You can override the path with `SUBAGENTS_CONFIG_PATH`.

If an OBO tool is selected and no forwarded token is present, the runtime raises a clear user-facing authorization error instead of falling back silently.

## Chainlit Token Commands

The Chainlit UI supports session-scoped token commands for OBO testing:

- `/token <databricks_access_token>`: stores a forwarded token for this chat session.
- `/clear-token`: clears the forwarded token from this chat session.

When set, the UI forwards the token to backend `/invocations` as the `x-forwarded-access-token` header.

## Core Architecture

High-level request path:

1. User message enters Chainlit UI.
2. Request reaches Databricks App endpoint.
3. MLflow Agent Server dispatches invoke or stream handlers.
4. Orchestrator selects tools and specialist agents.
5. Tools query Genie or serving endpoints.
6. Unified response is returned to the client.

For detailed architecture and component diagrams, see [docs/architecture.md](docs/architecture.md).

## Project Layout

- [backend/](backend): orchestrator runtime, handlers, request normalization, server startup
- [frontend/ui_app.py](frontend/ui_app.py): Chainlit bootstrap entrypoint
- [frontend/app/](frontend/app): modular frontend package (handlers, config, session, streaming, UI)
- [scripts/](scripts): quickstart, preflight, local start, discovery, and permission helpers
- [resources/multiagent_app.yml](resources/multiagent_app.yml): shared Databricks app resource definition
- [targets/](targets): target-specific deployment overlays
- [databricks.yml](databricks.yml): DAB bundle root configuration
- [docs/README.md](docs/README.md): architecture, design, and runbook documentation index

## Quick Start

Prerequisites:

- Python 3.11+
- uv
- Databricks CLI

Run locally:

```bash
uv run quickstart
uv run start-app
```

Validate and deploy:

```bash
databricks bundle validate -t dev --profile dev
databricks bundle deploy -t dev --profile dev
databricks bundle run multiagent-app --target dev
```

If bundle deploy fails due to Terraform provider registry availability, use the operational fallback documented in [docs/runbook.md](docs/runbook.md).

## Runtime Environment Variables

- `BACKEND_LOG_LEVEL`: backend log level (default `INFO`).
- `BACKEND_LOG_FORMAT`: Python logging format string for backend logs.
- `BACKEND_LOG_DATE_FORMAT`: datetime format used in backend logs.
- `MESSAGE_BUS_BACKEND`: `structured_logging` (default), `noop`, `kafka`, or `rabbitmq`.
- `MESSAGE_BUS_TOPIC`: topic name used by message bus backends (default `agent-lifecycle-events`).
- `MESSAGE_BUS_FAIL_OPEN`: when `true`, fallback to structured logging if bus init fails.
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (required for `MESSAGE_BUS_BACKEND=kafka`).
- `KAFKA_CLIENT_ID`: Kafka client id used by producer (default `multiagent-app`).
- `RABBITMQ_URL`: RabbitMQ AMQP URL (required for `MESSAGE_BUS_BACKEND=rabbitmq`).

## Documentation

- [docs/architecture.md](docs/architecture.md): high-level architecture and request flow
- [docs/design.md](docs/design.md): low-level module design and runtime behavior
- [docs/runbook.md](docs/runbook.md): deployment, operations, incident handling, rollback

## Current Status

- Development environment is active and user-accessible.
- Multi-agent routing across Genie and serving endpoints is implemented.
- Deployment pipeline supports dev, qa, stg, and prod target workflows.
- Operational controls and troubleshooting guidance are documented in the runbook.

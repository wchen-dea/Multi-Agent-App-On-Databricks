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
- Deployment-as-code: Databricks Declarative Automation Bundles with target overlays.
- Streaming-first UX: Chainlit frontend with incremental token streaming.

## Functionality Perspective

From a user and platform viewpoint, the app provides:

- Unified endpoint: A single app endpoint for multi-tool, multi-agent interaction.
- Dynamic routing: Requests are routed to Genie, serving endpoints, or app-based specialists.
- Real-time responses: Streaming responses for conversational latency.
- Configurable specialist set: Subagents can be added and validated through typed configuration.
- Environment isolation: dev, qa, stg, and prod with explicit target-specific settings.
- Operational fallback path: Direct apps deploy path when Terraform registry availability is degraded.

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
- [frontend/chainlit_app.py](frontend/chainlit_app.py): chat UI and backend proxy streaming
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

## Documentation

- [docs/architecture.md](docs/architecture.md): high-level architecture and request flow
- [docs/design.md](docs/design.md): low-level module design and runtime behavior
- [docs/runbook.md](docs/runbook.md): deployment, operations, incident handling, rollback

## Current Status

- Development environment is active and user-accessible.
- Multi-agent routing across Genie and serving endpoints is implemented.
- Deployment pipeline supports dev, qa, stg, and prod target workflows.
- Operational controls and troubleshooting guidance are documented in the runbook.


# Backend

Multi-agent orchestrator server. Exposes the MLflow Responses API (`/invocations`) via FastAPI/Uvicorn and routes user requests to one or more configured backends.

## Current Status (2026-07-01)

- Backend is running in dev Databricks Apps and reachable through the UI and API routes.
- Hosted runtime currently uses UI mode with backend port remapping handled by `scripts/start_app.py`.
- Genie routing requires SQL warehouse access plus Unity Catalog `USE CATALOG`/`USE SCHEMA` and `SELECT` on referenced tables.

## Files

| File | Description |
|---|---|
| `agent.py` | Orchestrator logic — subagent tool definitions, MCP server setup, `@invoke`/`@stream` handlers |
| `start_server.py` | FastAPI + MLflow `AgentServer` startup; entry point for `uv run start-server` |
| `evaluate_agent.py` | MLflow evaluation workflow using simulated conversations and LLM judges |
| `utils.py` | Helpers: MCP URL builder, session ID extraction, user workspace client, stream event processing |

## Configuration Required

Before running, edit `agent.py` and uncomment/configure entries in the `SUBAGENTS` list. Each entry becomes a tool the orchestrator can call:

| `type` | Required fields | When to use |
|---|---|---|
| `"genie"` | `space_id` | Query a Genie space for structured data (uses Databricks MCP server) |
| `"app"` | `endpoint` | Call another agent deployed as a Databricks App (Responses API) |
| `"serving_endpoint"` | `endpoint` | Call a Model Serving endpoint (must have task type `agent/v1/responses`) |

Each entry also requires a `name` (used as the tool function name) and a `description` (shown to the orchestrator for routing decisions).

Also update the orchestrator `instructions` and `model` near the bottom of `agent.py` to match your configured tools.

## Running

Started automatically by `uv run start-app`. To run the backend alone:

```sh
uv run start-server
uv run start-server --port 9000
uv run start-server --reload        # hot reload for development
uv run start-server --help          # all options
```

## Evaluation

```sh
uv run agent-evaluate
```

Runs simulated multi-turn conversations against the agent and scores them with MLflow LLM judges (safety, relevance, fluency, tool correctness, etc.). Edit `evaluate_agent.py` to add your own test cases and scorers.

## Key Dependencies

- `mlflow` — `AgentServer`, `@invoke`/`@stream` decorators, tracing, evaluation
- `openai-agents` — `Agent`, `Runner`, `function_tool`
- `databricks-openai` — `AsyncDatabricksOpenAI`, `McpServer`
- `fastapi` / `uvicorn` — HTTP server

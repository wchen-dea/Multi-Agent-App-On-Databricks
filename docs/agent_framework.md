# Multiagent App on Databricks: Developer Guide

Prefer pragmatic, incremental changes that keep local iteration fast and deployment predictable across `dev`, `qa`, `stg`, and `prod`.

## First-Time Setup

1. Check whether `.env` exists. If not, run:

```bash
uv run quickstart --profile PROFILE_NAME
```

2. Verify auth profile is valid:

```bash
databricks auth profiles
```

3. Always include the target profile in Databricks CLI commands:

```bash
databricks COMMAND --profile PROFILE_NAME
# or
DATABRICKS_CONFIG_PROFILE=PROFILE_NAME databricks COMMAND
```

Omitting the profile can silently target the wrong workspace.

## Discovering Available Resources

Before wiring new tools, discover what already exists in your workspace:

```bash
uv run discover-tools
```

This lists Genie spaces, serving endpoints, UC functions, and registered apps available to connect.

## Adding Tools to the Orchestrator

All tool types are configured in `backend/agent.py` via the `SUBAGENTS` list. Each entry becomes a callable tool the orchestrator can route to.

| Tool type | Config field | Notes |
| --------- | ------------ | ----- |
| Genie space | `type: "genie"`, `space_id` | Routed via Databricks MCP server |
| App agent | `type: "app"`, `endpoint` | Called via Responses API (`apps/<name>`) |
| Serving endpoint | `type: "serving_endpoint"`, `endpoint` | Must have task type `agent/v1/responses` |

After adding a tool entry, grant the corresponding resource permission in `resources/multiagent_app.yml` (shared default) and/or `targets/*.yml` (environment-specific override).

## Deployment

### Validate

```bash
databricks bundle validate -t dev --profile dev
databricks bundle validate -t qa --profile qa
databricks bundle validate -t stg --profile stg
databricks bundle validate -t prod --profile prd
```

### Deploy and start

```bash
databricks bundle deploy -t TARGET --profile PROFILE
databricks bundle run multiagent_app --target TARGET
```

### App name conflict

If deploy fails because the app already exists in the workspace:

```bash
# Bind the existing app to this bundle, then redeploy
databricks bundle deployment bind multiagent_app APP_NAME --auto-approve
databricks bundle deploy -t TARGET --profile PROFILE
```

To delete and recreate instead:

```bash
databricks apps delete APP_NAME --profile PROFILE
databricks bundle deploy -t TARGET --profile PROFILE
```

## Supervisor API

The Databricks Supervisor API runs tool selection and the agent loop server-side.

Use when:
- Connecting hosted tools (Genie, UC functions, serving endpoints)
- Offloading the agent loop to Databricks infrastructure

Limitations:
- All tools run as the app service principal
- Hosted tools and client-side function tools cannot be mixed in one request
- Inference parameters are restricted when tools are attached
- `stream` and `background` cannot both be `true`
- Background mode maximum execution time is 30 minutes

## Long-Term Memory

Managed memory uses Databricks memory-store APIs (currently beta). Use it for cross-session agent memory without operating custom storage infrastructure. Configure via environment variables and the `resources/multiagent_app.yml` bundle resource.

## Agent Evaluation

Run evaluation locally against the configured agent:

```bash
uv run agent-evaluate
```

Edit `backend/evaluate_agent.py` to define test cases and scoring criteria. Evaluation uses MLflow LLM judges (safety, relevance, fluency, tool correctness, etc.).

## Quick Reference

| Task | Command |
| ---- | ------- |
| Initial setup | `uv run quickstart` |
| Discover resources | `uv run discover-tools` |
| Run locally | `uv run start-app` |
| Backend only | `uv run start-server --reload` |
| Validate bundle | `databricks bundle validate -t TARGET --profile PROFILE` |
| Deploy | `databricks bundle deploy -t TARGET --profile PROFILE` |
| Start deployed app | `databricks bundle run multiagent_app --target TARGET` |
| View app logs | `databricks apps logs APP_NAME --follow` |
| Run evaluation | `uv run agent-evaluate` |

## Key Files

| File | Purpose |
| ---- | ------- |
| `backend/agent.py` | Orchestrator logic, `SUBAGENTS` config, invoke/stream handlers |
| `backend/start_server.py` | FastAPI and MLflow Agent Server startup |
| `backend/evaluate_agent.py` | Evaluation test cases and scoring |
| `databricks.yml` | Bundle root config and shared variables |
| `resources/multiagent_app.yml` | Shared app config and baseline resource permissions |
| `targets/dev.yml` | Dev workspace, variables, and permission overrides |
| `targets/qa.yml` | QA workspace, variables, and permission overrides |
| `targets/stg.yml` | Staging workspace, variables, and permission overrides |
| `targets/prod.yml` | Prod workspace, variables, and permission overrides |
| `bitbucket-pipelines.yml` | CI/CD validate, deploy, and run flow |
| `scripts/quickstart.py` | Interactive setup automation |
| `scripts/discover_tools.py` | Workspace resource discovery |

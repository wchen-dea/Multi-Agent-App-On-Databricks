# Agent Development Guide

This project is maintained as an MVP-first template. Prefer pragmatic, incremental changes that keep local iteration fast and deployment predictable across `dev`, `qa`, `stg`, and `prod`.

## Mandatory First Actions

Ask the user these questions before implementation:

1. App deployment target:
   Do you have an existing Databricks app you want to deploy to, or should we create a new one? If existing, what is the app name?
2. If the user mentions memory or persistence:
   For memory capabilities, do you have an existing Lakebase instance? If so, what is the instance name?

Then set up the environment:

1. Read the quickstart skill at `../.claude/skills/quickstart/SKILL.md`.
2. Check whether `.env` exists.
3. If `.env` does not exist, run:

```bash
uv run quickstart --profile PROFILE_NAME
```

1. Verify auth profile validity:

```bash
databricks auth profiles
```

Critical rule: all Databricks CLI commands must include the target profile.

```bash
databricks COMMAND --profile PROFILE_NAME
# or
DATABRICKS_CONFIG_PROFILE=PROFILE_NAME databricks COMMAND
```

Why: without an explicit profile, commands may hit the wrong workspace and cause misleading not-found errors.

## Understanding User Goals

Ask:

1. What is the agent's purpose?
2. What data or tools are required?
3. Are there specific Databricks resources to connect?

Use resource discovery when needed:

```bash
uv run discover-tools
```

Then map requested capabilities to tool and permission changes in bundle config.

## Deployment Errors

If `databricks bundle deploy` fails with app name conflict:

- Ask whether to bind existing app or delete and recreate.
- If bind: follow `../.claude/skills/deploy/SKILL.md`.
- If delete and recreate:

```bash
databricks apps delete APP_NAME --profile PROFILE_NAME
```

## Supervisor API Notes

Supervisor API runs tool selection and loop server-side in Databricks.

Use when:

- User wants hosted tools (Genie, UC functions, hosted endpoints)
- User wants Databricks-managed loop execution

Limitations:

- Tools run as app service principal
- Hosted tools and client-side function tools cannot be mixed in one request
- Inference parameters are restricted when tools are attached
- `stream` and `background` cannot both be true
- Background mode max execution time is 30 minutes

Skills:

- `../.claude/skills/supervisor-api/SKILL.md`
- `../.claude/skills/supervisor-api-background-mode/SKILL.md`

## Long-Term Memory (Managed)

Managed memory uses Databricks memory-store APIs and is currently beta.

Use when the user needs cross-session memory without operating custom storage.

Skills:

- `../.claude/skills/managed-memory/SKILL.md`

## Agent Evaluation

For evaluation workflows, recommend MLflow skills:

- [MLflow Skills](https://github.com/mlflow/skills)

Built-in local evaluation command:

```bash
uv run agent-evaluate
```

## Available Skills

Read the relevant skill file before executing related tasks.

| Task | Skill | Path |
| ---- | ----- | ---- |
| Setup and auth | quickstart | `../.claude/skills/quickstart/SKILL.md` |
| Discover resources | discover-tools | `../.claude/skills/discover-tools/SKILL.md` |
| Create resources | create-tools | `../.claude/skills/create-tools/SKILL.md` |
| Deploy | deploy | `../.claude/skills/deploy/SKILL.md` |
| Add tools and permissions | add-tools | `../.claude/skills/add-tools/SKILL.md` |
| Local run and testing | run-locally | `../.claude/skills/run-locally/SKILL.md` |
| Modify agent | modify-agent | `../.claude/skills/modify-agent/SKILL.md` |
| Managed memory | managed-memory | `../.claude/skills/managed-memory/SKILL.md` |
| Supervisor API | supervisor-api | `../.claude/skills/supervisor-api/SKILL.md` |
| Background mode | supervisor-api-background-mode | `../.claude/skills/supervisor-api-background-mode/SKILL.md` |

## Quick Commands

| Task | Command |
| ---- | ------- |
| Setup | `uv run quickstart` |
| Discover tools | `uv run discover-tools` |
| Run locally | `uv run start-app` |
| Deploy app | `databricks bundle deploy && databricks bundle run agent_openai_agents_sdk_multiagent` |
| View logs | `databricks apps logs APP_NAME --follow` |

Environment-specific examples:

- `databricks bundle validate -t dev --profile dev`
- `databricks bundle validate -t qa --profile qa`
- `databricks bundle validate -t stg --profile stg`
- `databricks bundle validate -t prod --profile prd`
- `databricks bundle deploy -t TARGET_NAME --profile PROFILE_NAME`

## Key Files

| File | Purpose |
| ---- | ------- |
| `agent_server/agent.py` | Orchestrator logic, tools, and variable configuration |
| `agent_server/start_server.py` | FastAPI and MLflow Agent Server startup |
| `agent_server/evaluate_agent.py` | Evaluation workflow |
| `databricks.yml` | Bundle root config and shared variables |
| `resources/app.yml` | Shared app config and baseline permissions |
| `targets/dev.yml` | Dev-specific workspace, variables, and overrides |
| `targets/qa.yml` | QA-specific workspace, variables, and overrides |
| `targets/stg.yml` | Staging-specific workspace, variables, and overrides |
| `targets/prod.yml` | Prod-specific workspace, variables, and overrides |
| `bitbucket-pipelines.yml` | CI/CD validate, deploy, and run flow |
| `scripts/quickstart.py` | Setup automation script |
| `scripts/discover_tools.py` | Resource discovery script |

## Agent Framework Capabilities

When adding any tool, also grant permissions in bundle config. Use shared defaults in `resources/app.yml` and target-specific overrides in `targets/*.yml`.

Tool types:

1. Unity Catalog function tools
2. Agent code tools
3. MCP tools

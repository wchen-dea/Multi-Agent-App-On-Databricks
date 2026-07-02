---
name: quickstart
description: "Initialize local Databricks development for this repository. Use when: first setup, auth/profile setup, .env bootstrapping, or MLflow experiment setup."
---

# Quickstart

Use this skill to set up local development for this project.

## When to Use

- First run on a new machine
- `.env` is missing or invalid
- Databricks authentication/profile is not configured
- `MLFLOW_EXPERIMENT_ID` is missing

## Commands

```bash
uv run quickstart
```

Common variants:

```bash
uv run quickstart --profile <profile>
uv run quickstart --host https://<workspace-host>
uv run quickstart --app-name <existing-app-name>
uv run quickstart --skip-lakebase
uv run quickstart --help
```

## What This Configures

- Databricks profile selection or creation
- `.env` defaults for local execution
- MLflow tracking/experiment configuration
- Optional app binding for existing Databricks Apps

## Verify Setup

```bash
databricks auth profiles
uv run preflight
uv run start-app
```

## Notes

- Prefer OAuth profile auth over hard-coded tokens.
- If auth fails, re-run `databricks auth login --profile <profile>` and retry.
- After quickstart, continue with `run-locally` or `deploy`.

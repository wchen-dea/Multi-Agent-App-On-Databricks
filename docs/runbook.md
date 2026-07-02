# Multiagent App on Databricks: Runbook (Operations)

## Purpose

Define operational procedures for validation, deployment, verification, incident response, and rollback.

## Scope

This document covers deployment and operations only. High-level system context is in `docs/architecture.md`, and implementation details are in `docs/design.md`.

## Current Status (2026-07-01)

- Dev app is running and user-accessible.
- Hosted startup uses UI mode with backend internal port remapping.
- Bundle validation is stable.
- Deployment can fail intermittently when Terraform provider registry is unreachable.
- Fallback workflow is in active use when registry outage occurs.

## Main Content

### Pre-Deployment Checklist

- Confirm target (`dev` / `qa` / `stg` / `prod`) and CLI profile.
- Confirm target variables in `targets/*.yml` are correct.
- Confirm Databricks credentials/secrets are available for target.
- Validate bundle before deploy.

### Standard Deployment Procedure

#### 1) Validate bundle

```bash
databricks bundle validate -t dev --profile dev
databricks bundle validate -t qa --profile qa
databricks bundle validate -t stg --profile stg
databricks bundle validate -t prod --profile prd
```

#### 2) Deploy

```bash
databricks bundle deploy -t TARGET --profile PROFILE
```

#### 3) Start or restart runtime

```bash
databricks bundle run multiagent-app --target TARGET
```

### Fallback Deployment Procedure

Use this procedure when `bundle deploy` fails due to Terraform provider registry availability.

```bash
databricks bundle sync -t TARGET --profile PROFILE
APP_SRC=$(databricks apps get APP_NAME --output json --profile PROFILE | jq -r '.default_source_code_path')
databricks apps deploy APP_NAME --profile PROFILE --source-code-path "$APP_SRC" --mode SNAPSHOT
```

### Existing App Conflict

Use this procedure when the app already exists and deployment cannot reconcile state:

```bash
databricks bundle deployment bind multiagent-app APP_NAME --auto-approve
databricks bundle deploy -t TARGET --profile PROFILE
```

Alternative recreate path:

```bash
databricks apps delete APP_NAME --profile PROFILE
databricks bundle deploy -t TARGET --profile PROFILE
```

### Post-Deploy Verification

- Non-streaming request succeeds.
- Streaming request succeeds.
- Tool routing behaves as expected.
- No startup crash loop.
- Logs do not contain authentication or missing-resource errors.

### Local Operations

#### Local startup

```bash
uv run start-app
```

#### Backend-only

```bash
uv run start-server --reload
uv run start-app --no-ui
```

#### Preflight and evaluation

```bash
uv run preflight
uv run agent-evaluate
```

### Incident Triage

1. Identify impacted environment.
2. Determine latest deploy source (manual or pipeline).
3. Review deployment output and app logs.
4. Verify credentials, app identities, and permissions.
5. Decide rollback vs forward fix.

### Common Failure Patterns

- Missing CI secrets for environment.
- Terraform registry unreachable.
- Deploy completed but runtime not restarted.
- Missing Unity Catalog grants for Genie query paths.
- Invalid local credentials in `.env` (for example stale `DATABRICKS_TOKEN`).

### Rollback

#### Pipeline rollback

- Redeploy the last known good commit through CI.

#### Manual rollback

```bash
databricks bundle deploy -t TARGET --profile PROFILE
databricks bundle run multiagent-app --target TARGET
```

Deploy a known good revision.

### Change Control

Before:

- Validate target configuration and secrets.

During:

- Use one deployment path per change.
- Capture commit and deployment output.

After:

- Run post-deploy verification.
- Record outcome and follow-up actions.

## Related Docs

- `docs/architecture.md`: high-level architecture
- `docs/design.md`: low-level design

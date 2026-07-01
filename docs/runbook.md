# Multiagent App on Databricks: Runbook

## Purpose

This runbook provides standard operating procedures for running, deploying, validating, and recovering the Multiagent App on Databricks MVP across `dev`, `qa`, `stg`, and `prod`.

## Scope

Covers:

- Local development startup and checks
- Databricks Declarative Automation Bundles validation and deployment
- Bitbucket pipeline deployment behavior
- Post-deploy verification
- Incident triage and rollback

Does not cover:

- Full enterprise SRE process integration
- Custom organization-specific on-call escalation tooling

## System Summary

- Runtime: MLflow Agent Server + OpenAI Agents SDK
- Deploy model: Databricks Declarative Automation Bundles
- Shared resource config: `resources/app.yml`
- Environment overrides: `targets/dev.yml`, `targets/qa.yml`, `targets/stg.yml`, `targets/prod.yml`
- CI/CD: `bitbucket-pipelines.yml`

## Environments

| Environment | Target | Mode | Profile |
| ---- | ---- | ---- | ---- |
| Development | dev | development | dev |
| QA | qa | development | qa |
| Staging | stg | production | stg |
| Production | prod | production | prd |

## Required Inputs

Before any deployment, ensure these are correct:

- Target-specific variables in `targets/*.yml`:
  - `app_name`
  - `genie_space_id`
  - `knowledge_assistant_endpoint_name`
  - `serving_endpoint_name`
  - `target_app_name`
- Databricks CLI profile authentication is valid for the target workspace
- Bitbucket deployment secrets exist for each environment:
  - `DATABRICKS_HOST_DEV`, `DATABRICKS_CLIENT_ID_DEV`, `DATABRICKS_CLIENT_SECRET_DEV`
  - `DATABRICKS_HOST_QA`, `DATABRICKS_CLIENT_ID_QA`, `DATABRICKS_CLIENT_SECRET_QA`
  - `DATABRICKS_HOST_STG`, `DATABRICKS_CLIENT_ID_STG`, `DATABRICKS_CLIENT_SECRET_STG`
  - `DATABRICKS_HOST_PROD`, `DATABRICKS_CLIENT_ID_PROD`, `DATABRICKS_CLIENT_SECRET_PROD`

## Local Operations

### Start locally

```bash
uv run start-app
```

### Backend-only modes

```bash
uv run start-server --reload
uv run start-server --port 8001
uv run start-server --workers 4
```

### Preflight checks

```bash
uv run preflight
uv run agent-evaluate
```

### Success criteria

- Local endpoint responds on expected port
- Streaming and non-streaming requests complete successfully
- No startup exceptions in server output

## Manual Deployment Procedure

### 1) Validate bundle

```bash
databricks bundle validate -t dev --profile dev
databricks bundle validate -t qa --profile qa
databricks bundle validate -t stg --profile stg
databricks bundle validate -t prod --profile prd
```

### 2) Deploy bundle

```bash
databricks bundle deploy -t dev --profile dev
databricks bundle deploy -t qa --profile qa
databricks bundle deploy -t stg --profile stg
databricks bundle deploy -t prod --profile prd
```

### 3) Restart app runtime

```bash
databricks bundle run agent_openai_agents_sdk_multiagent --target dev
```

Replace `dev` with `qa`, `stg`, or `prod` as required.

## Bitbucket Deployment Procedure

The pipeline resolves target from deployment environment or branch and loads environment-suffixed secrets.

Branch mapping:

- `dev` -> `dev`
- `qa` -> `qa`
- `stg` -> `stg`
- `prod` -> `prod`

Pipeline stages (shared definition):

1. Install Databricks CLI
2. Resolve deployment target
3. Export target-specific credentials
4. `databricks bundle validate`
5. `databricks bundle deploy`
6. `databricks bundle run agent_openai_agents_sdk_multiagent`

## Post-Deploy Verification

### Functional checks

- Send a non-streaming request and confirm valid response
- Send a streaming request and confirm event stream continuity
- Confirm routing to expected backend for at least one known query path

### Configuration checks

- Verify target app name is correct
- Verify Genie space and serving endpoint resources are reachable
- Verify app-to-app permission (`CAN_USE`) is effective where configured

### Basic health checks

- No immediate crash/restart loops
- Logs contain no authentication or missing-resource errors

## Rollback Procedure

Use one of the following methods:

### Option A: Redeploy known good commit through Bitbucket

1. Identify last known good commit for the target branch
2. Trigger deployment from that commit
3. Verify using post-deploy checks

### Option B: Redeploy known good local revision manually

1. Checkout known good revision locally
2. Run:

```bash
databricks bundle deploy -t TARGET_NAME --profile PROFILE_NAME
databricks bundle run agent_openai_agents_sdk_multiagent --target TARGET_NAME
```

1. Verify using post-deploy checks

## Incident Response

### Severity guidance

- Sev 1: Production unavailable or severe user impact
- Sev 2: Major degraded function with workaround
- Sev 3: Non-critical defect, no immediate customer block

### Triage checklist

1. Identify impacted environment (`dev`/`qa`/`stg`/`prod`)
2. Check latest deploy event (manual or pipeline)
3. Review app logs and deployment output
4. Confirm target secrets and auth profile validity
5. Confirm resource identities still exist and permissions are intact
6. Decide rollback vs hotfix

### Common failure patterns

- Missing secret for environment suffix
  - Symptom: pipeline exits with missing required secret
  - Action: add missing `DATABRICKS_*_ENV` variables
- App exists but deployment cannot reconcile
  - Symptom: app conflict or inconsistent apply errors
  - Action: bind existing app to bundle, then redeploy
- Deploy succeeded but old behavior persists
  - Symptom: code/config not reflected at runtime
  - Action: run `databricks bundle run agent_openai_agents_sdk_multiagent --target TARGET_NAME`
- Query returns auth/redirect errors
  - Symptom: query failures with 302/auth behavior
  - Action: verify OAuth token flow and endpoint URL

## Operational Change Checklist

Before change:

- Confirm target and workspace
- Confirm required secrets and permissions
- Validate bundle for target

During change:

- Deploy using one path only (manual or CI)
- Capture deploy output and commit identifier

After change:

- Run post-deploy verification
- Record outcome and any follow-up actions

## Ownership and Escalation

Maintain this section with team details:

- Service owner: TEAM_OWNER
- Primary on-call: PRIMARY_ONCALL
- Secondary on-call: SECONDARY_ONCALL
- Escalation channel: INCIDENT_CHANNEL
- Escalation SLA: ESCALATION_SLA

## Revision History

- 2026-06-30: Initial runbook created for MVP operations and multi-target deployment flow.

## Related Docs

- `README.md`: project overview and onboarding flow
- `docs/agent_framework.md`: developer workflow and implementation guidance
- `docs/architecture.md`: component and request-flow details

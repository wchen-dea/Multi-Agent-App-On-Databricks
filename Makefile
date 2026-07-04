.PHONY: help test build-wheel validate-dev bundle-deploy-dev import-dev deploy-dev redeploy-dev health-dev logs-dev status-dev

PROFILE ?= DEFAULT
TARGET ?= dev
APP_NAME ?= multiagent-app-dev

help:
	@printf "Local dev Databricks app workflow\n\n"
	@printf "Targets:\n"
	@printf "  make test              Run local test suite\n"
	@printf "  make build-wheel       Build wheel-first app source payload\n"
	@printf "  make validate-dev      Validate Databricks bundle for dev\n"
	@printf "  make bundle-deploy-dev Try bundle deploy for dev (may fail on Terraform registry)\n"
	@printf "  make import-dev        Upload .databricks_app_source into the app workspace path\n"
	@printf "  make deploy-dev        Deploy the uploaded app source with Databricks Apps\n"
	@printf "  make redeploy-dev      Build, validate, import, deploy, and verify health\n"
	@printf "  make health-dev        Verify app deployment/app state is healthy\n"
	@printf "  make status-dev        Print current app status JSON\n"
	@printf "  make logs-dev          Tail recent app logs\n"

test:
	uv run pytest -q

build-wheel:
	uv run prepare-app-source

validate-dev:
	databricks bundle validate -t "$(TARGET)" --profile "$(PROFILE)"

bundle-deploy-dev:
	@databricks bundle deploy -t "$(TARGET)" --profile "$(PROFILE)" || \
		(printf "bundle deploy failed; use make redeploy-dev for the Terraform-free fallback path\n" && exit 1)

import-dev: build-wheel
	@APP_SRC="$$(databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json | jq -r '.default_source_code_path')"; \
	if [ -z "$$APP_SRC" ] || [ "$$APP_SRC" = "null" ]; then \
		printf "Could not resolve default_source_code_path for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	databricks workspace import-dir .databricks_app_source "$$APP_SRC" --overwrite --profile "$(PROFILE)"

deploy-dev:
	@APP_SRC="$$(databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json | jq -r '.default_source_code_path')"; \
	if [ -z "$$APP_SRC" ] || [ "$$APP_SRC" = "null" ]; then \
		printf "Could not resolve default_source_code_path for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	databricks apps deploy "$(APP_NAME)" --profile "$(PROFILE)" --source-code-path "$$APP_SRC" --mode SNAPSHOT

redeploy-dev: build-wheel validate-dev import-dev deploy-dev health-dev

health-dev:
	@APP_JSON="$$(databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json)"; \
	DEPLOY_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.active_deployment.status.state')"; \
	APP_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.app_status.state')"; \
	COMPUTE_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.compute_status.state')"; \
	SOURCE_PATH="$$(printf "%s" "$$APP_JSON" | jq -r '.default_source_code_path')"; \
	printf "deployment=%s\napp=%s\ncompute=%s\nsource=%s\n" "$$DEPLOY_STATE" "$$APP_STATE" "$$COMPUTE_STATE" "$$SOURCE_PATH"; \
	if [ "$$DEPLOY_STATE" != "SUCCEEDED" ] || [ "$$APP_STATE" != "RUNNING" ]; then \
		printf "App health check failed for $(APP_NAME)\n" >&2; \
		printf "%s" "$$APP_JSON" | jq -r '.active_deployment.status, .app_status, .compute_status' >&2; \
		exit 1; \
	fi

status-dev:
	databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json

logs-dev:
	databricks apps logs "$(APP_NAME)" --tail-lines 120 --profile "$(PROFILE)"
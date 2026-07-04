SHELL := /bin/sh

.PHONY: help test build-app-source validate bundle-deploy import ensure-running deploy redeploy health smoke logs status

PROFILE ?= DEFAULT
TARGET ?= dev
APP_NAME ?= multiagent-app-$(TARGET)
APP_START_MAX_ATTEMPTS ?= 30
APP_START_POLL_SECONDS ?= 2

APP_GET_JSON = databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json

help:
	@printf "Local dev Databricks app workflow\n\n"
	@printf "Targets:\n"
	@printf "  make test              Run local test suite\n"
	@printf "  make build-app-source  Build wheel + React UI app source payload\n"
	@printf "  make validate          Validate Databricks bundle for TARGET\n"
	@printf "  make bundle-deploy     Try bundle deploy for TARGET (may fail on Terraform registry)\n"
	@printf "  make import            Upload .databricks_app_source into app workspace path\n"
	@printf "  make deploy            Deploy uploaded app source with Databricks Apps\n"
	@printf "  make redeploy          Build, validate, import, deploy, and verify health\n"
	@printf "  make health            Verify app deployment/app state is healthy\n"
	@printf "  make smoke            Smoke-check app URL, React index shell, and /invocations route\n"
	@printf "  make status            Print current app status JSON\n"
	@printf "  make logs              Tail recent app logs\n"
	@printf "\n"
	@printf "Examples:\n"
	@printf "  make redeploy TARGET=dev APP_NAME=multiagent-app-dev\n"
	@printf "  make health TARGET=qa APP_NAME=multiagent-app-qa\n"

test:
	uv run pytest -q

build-app-source:
	uv run prepare-app-source

validate:
	databricks bundle validate -t "$(TARGET)" --profile "$(PROFILE)"

bundle-deploy:
	@databricks bundle deploy -t "$(TARGET)" --profile "$(PROFILE)" || \
		(printf "bundle deploy failed; use make redeploy for the Terraform-free fallback path\n" && exit 1)

import: build-app-source
	@APP_JSON="$$($(APP_GET_JSON))"; \
	APP_SRC="$$(printf "%s" "$$APP_JSON" | jq -r '.default_source_code_path')"; \
	if [ -z "$$APP_SRC" ] || [ "$$APP_SRC" = "null" ]; then \
		printf "Could not resolve default_source_code_path for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	databricks workspace import-dir .databricks_app_source "$$APP_SRC" --overwrite --profile "$(PROFILE)"

ensure-running:
	@databricks apps start "$(APP_NAME)" --profile "$(PROFILE)" >/dev/null 2>&1 || true; \
	APP_STATE=""; \
	ATTEMPT=0; \
	while [ $$ATTEMPT -lt "$(APP_START_MAX_ATTEMPTS)" ]; do \
		APP_STATE="$$($(APP_GET_JSON) | jq -r '.app_status.state')"; \
		if [ "$$APP_STATE" = "RUNNING" ]; then \
			exit 0; \
		fi; \
		ATTEMPT=$$((ATTEMPT + 1)); \
		sleep "$(APP_START_POLL_SECONDS)"; \
	done; \
	printf "App $(APP_NAME) is not RUNNING (state=%s)\n" "$$APP_STATE" >&2; \
	exit 1

deploy: ensure-running
	@APP_JSON="$$($(APP_GET_JSON))"; \
	APP_SRC="$$(printf "%s" "$$APP_JSON" | jq -r '.default_source_code_path')"; \
	if [ -z "$$APP_SRC" ] || [ "$$APP_SRC" = "null" ]; then \
		printf "Could not resolve default_source_code_path for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	databricks apps deploy "$(APP_NAME)" --profile "$(PROFILE)" --source-code-path "$$APP_SRC" --mode SNAPSHOT

redeploy: build-app-source validate import deploy health

health:
	@APP_JSON="$$($(APP_GET_JSON))"; \
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

smoke:
	@APP_JSON="$$($(APP_GET_JSON))"; \
	APP_URL="$$(printf "%s" "$$APP_JSON" | jq -r '.url')"; \
	APP_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.app_status.state')"; \
	if [ -z "$$APP_URL" ] || [ "$$APP_URL" = "null" ]; then \
		printf "Could not resolve app URL for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	if [ "$$APP_STATE" != "RUNNING" ]; then \
		printf "App $(APP_NAME) is not RUNNING (state=%s)\n" "$$APP_STATE" >&2; \
		exit 1; \
	fi; \
	ROOT_TMP="$$(mktemp)"; \
	ROOT_CODE="$$(curl --noproxy '*' -sS -o "$$ROOT_TMP" -w '%{http_code}' "$$APP_URL")"; \
	printf "smoke.root.url=%s\nsmoke.root.code=%s\n" "$$APP_URL" "$$ROOT_CODE"; \
	case "$$ROOT_CODE" in \
		200|302|401|403) ;; \
		*) printf "Unexpected root status code: %s\n" "$$ROOT_CODE" >&2; rm -f "$$ROOT_TMP"; exit 1 ;; \
	esac; \
	if [ "$$ROOT_CODE" = "200" ]; then \
		if ! grep -q '<div id="root"></div>' "$$ROOT_TMP"; then \
			printf "Root page does not contain expected React shell marker\n" >&2; \
			rm -f "$$ROOT_TMP"; \
			exit 1; \
		fi; \
	fi; \
	rm -f "$$ROOT_TMP"; \
	INV_TMP="$$(mktemp)"; \
	INV_CODE="$$(curl --noproxy '*' -sS -o "$$INV_TMP" -w '%{http_code}' -X POST "$${APP_URL%/}/invocations" -H 'content-type: application/json' --data '{"input":[{"role":"user","content":"ping"}],"stream":false}')"; \
	printf "smoke.invocations.code=%s\n" "$$INV_CODE"; \
	if [ "$$INV_CODE" = "404" ] || [ "$$INV_CODE" = "000" ]; then \
		printf "/invocations route is not reachable through React UI proxy\n" >&2; \
		rm -f "$$INV_TMP"; \
		exit 1; \
	fi; \
	rm -f "$$INV_TMP"; \
	printf "Smoke checks passed for $(APP_NAME)\n"

status:
	$(APP_GET_JSON)

logs:
	databricks apps logs "$(APP_NAME)" --tail-lines 120 --profile "$(PROFILE)"
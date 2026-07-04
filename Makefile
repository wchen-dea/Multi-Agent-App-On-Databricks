.PHONY: help test build-app-source build-wheel validate-dev bundle-deploy-dev import-dev deploy-dev redeploy-dev health-dev smoke-dev logs-dev status-dev

PROFILE ?= DEFAULT
TARGET ?= dev
APP_NAME ?= multiagent-app-dev

help:
	@printf "Local dev Databricks app workflow\n\n"
	@printf "Targets:\n"
	@printf "  make test              Run local test suite\n"
	@printf "  make build-app-source  Build wheel + React UI app source payload\n"
	@printf "  make build-wheel       Backward-compatible alias for build-app-source\n"
	@printf "  make validate-dev      Validate Databricks bundle for dev\n"
	@printf "  make bundle-deploy-dev Try bundle deploy for dev (may fail on Terraform registry)\n"
	@printf "  make import-dev        Upload .databricks_app_source into the app workspace path\n"
	@printf "  make deploy-dev        Deploy the uploaded app source with Databricks Apps\n"
	@printf "  make redeploy-dev      Build, validate, import, deploy, and verify health\n"
	@printf "  make health-dev        Verify app deployment/app state is healthy\n"
	@printf "  make smoke-dev         Smoke-check app URL, React index shell, and /invocations route\n"
	@printf "  make status-dev        Print current app status JSON\n"
	@printf "  make logs-dev          Tail recent app logs\n"

test:
	uv run pytest -q

build-app-source:
	uv run prepare-app-source

build-wheel: build-app-source

validate-dev:
	databricks bundle validate -t "$(TARGET)" --profile "$(PROFILE)"

bundle-deploy-dev:
	@databricks bundle deploy -t "$(TARGET)" --profile "$(PROFILE)" || \
		(printf "bundle deploy failed; use make redeploy-dev for the Terraform-free fallback path\n" && exit 1)

import-dev: build-app-source
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
	databricks apps start "$(APP_NAME)" --profile "$(PROFILE)" >/dev/null 2>&1 || true; \
	APP_STATE=""; \
	for _ in $$(seq 1 30); do \
		APP_STATE="$$(databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json | jq -r '.app_status.state')"; \
		if [ "$$APP_STATE" = "RUNNING" ]; then \
			break; \
		fi; \
		sleep 2; \
	done; \
	if [ "$$APP_STATE" != "RUNNING" ]; then \
		printf "App $(APP_NAME) is not RUNNING (state=%s)\n" "$$APP_STATE" >&2; \
		exit 1; \
	fi; \
	databricks apps deploy "$(APP_NAME)" --profile "$(PROFILE)" --source-code-path "$$APP_SRC" --mode SNAPSHOT

redeploy-dev: build-app-source validate-dev import-dev deploy-dev health-dev

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

smoke-dev:
	@APP_JSON="$$(databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json)"; \
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

status-dev:
	databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json

logs-dev:
	databricks apps logs "$(APP_NAME)" --tail-lines 120 --profile "$(PROFILE)"
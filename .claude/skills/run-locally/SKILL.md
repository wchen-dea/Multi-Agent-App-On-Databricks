---
name: run-locally
description: "Run and validate the app locally. Use when: starting backend/frontend, testing invocations, or troubleshooting local runtime issues."
---

# Run Locally

## Start Modes

Full local app (backend + Chainlit UI):

```bash
uv run start-app
```

Backend only:

```bash
uv run start-server --reload
uv run start-server --port 8001
uv run start-server --workers 4
```

## Validate Runtime

```bash
uv run preflight
uv run agent-evaluate
```

## Test API

Non-streaming:

```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{"input":[{"role":"user","content":"hi"}]}'
```

Streaming:

```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{"input":[{"role":"user","content":"hi"}],"stream":true}'
```

## Troubleshooting

- Port conflict: change `--port` or stop existing process.
- Auth errors: run `uv run quickstart` and verify profile.
- Missing deps: run `uv sync`.
- Experiment errors: confirm `.env` contains valid `MLFLOW_EXPERIMENT_ID` and `MLFLOW_TRACKING_URI`.

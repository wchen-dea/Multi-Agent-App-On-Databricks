---
name: modify-agent
description: "Modify orchestrator behavior, subagent routing, and request handling for this repository. Use when: changing model/instructions, adding subagents, or adjusting runtime flow."
---

# Modify Agent

## Primary Files (This Repo)

- `backend/agent.py`: invoke/stream handlers and entry wiring
- `backend/orchestrator.py`: tool/server construction and orchestrator creation
- `backend/subagent_config.py`: typed subagent definitions and validation
- `backend/request_utils.py`: request normalization and MCP error extraction
- `backend/utils.py`: runtime helpers (workspace host, ids, stream normalization)

## Common Changes

Change orchestrator behavior:

- Update prompts/model/orchestration logic in `backend/orchestrator.py`.

Add or edit subagents:

- Update `RAW_SUBAGENTS` in `backend/subagent_config.py`.
- Supported types: `genie`, `serving_endpoint`, `app`.
- Required fields:
  - `genie`: `space_id`
  - `serving_endpoint` and `app`: `endpoint`

Adjust request/response shaping:

- `backend/request_utils.py` for input normalization and surfaced errors.

## Validate After Changes

```bash
python -m py_compile backend/*.py scripts/*.py frontend/*.py
uv run preflight
uv run start-app
```

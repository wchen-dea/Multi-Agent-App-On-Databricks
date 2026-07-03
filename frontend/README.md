# Frontend README

## Overview

The frontend is a Chainlit chat UI that:

- captures user prompts and chat history,
- streams responses from the backend `/invocations` endpoint,
- supports optional forwarded user token commands for OBO flows.

Primary entrypoint:

- `frontend/ui_app.py`

## Structure

- `frontend/ui_app.py`: thin Chainlit bootstrap module.
- `frontend/app/handlers.py`: chat lifecycle and backend proxy streaming.
- `frontend/app/config.py`: typed frontend runtime settings from environment.
- `frontend/app/session.py`: session state for chat history and forwarded token.
- `frontend/app/commands.py`: slash command parsing (`/token`, `/clear-token`).
- `frontend/app/stream_events.py`: stream event parsing and delta extraction.
- `frontend/app/ui_content.py`: welcome content, starter prompts, source badges.

## Local Run

Recommended from repo root:

```bash
uv run start-app
```

This starts backend + frontend together and configures `API_PROXY` automatically.

Frontend-only run (when backend is already running):

```bash
chainlit run frontend/ui_app.py --port 3000
```

## For New Developers

Use this workflow when iterating on chat UX or stream rendering:

1. Start full stack from repo root: `uv run start-app`
2. Edit files under `frontend/app/`
3. Re-run and verify behavior in the chat UI

Frontend code paths most often changed:

- `frontend/app/handlers.py`: message loop and stream consumption.
- `frontend/app/ui_content.py`: welcome panel and prompt starters.
- `frontend/app/stream_events.py`: event parsing and text delta extraction.

Tip:

- Run with backend together unless you are intentionally isolating frontend behavior.

## Environment Variables

- `API_PROXY`: backend invocations URL. Default: `http://localhost:8000/invocations`.
- `CHAT_GREETING`: greeting shown in chat welcome panel.
- `CHAT_PROXY_TIMEOUT_SECONDS`: backend request timeout in seconds.
- `CHAT_COMPANY_NAME`: UI branding company name.
- `CHAT_COMPANY_TAGLINE`: UI branding tagline.
- `CHAT_APP_PORT`: preferred local frontend port used by `start-app`.

## Token Forwarding Commands

In chat, operators can control forwarded token state per session:

- `/token <databricks_access_token>`: save token for this chat session.
- `/clear-token`: remove token for this chat session.

When set, the token is sent to backend as header `x-forwarded-access-token`.

## For Operators

Use this checklist for auth-routing validation:

1. Start app: `uv run start-app`
2. In chat, set a token: `/token <databricks_access_token>`
3. Run a request that should use OBO-backed tools
4. Clear token: `/clear-token`
5. Re-run request and confirm expected authorization behavior

Operational notes:

- Session token state is per chat session.
- Use `backend.log` and `frontend.log` for incident triage.

## Troubleshooting

- Cannot connect to backend:
  - Ensure backend is running (`uv run start-server`) or use `uv run start-app`.
  - Verify `API_PROXY` points to a valid `/invocations` URL.
- Empty or broken stream output:
  - Check `backend.log` and `frontend.log` from `start-app`.
- Port in use:
  - Set `CHAT_APP_PORT` to a free port in `.env`.

# React UI (Primary Frontend)

This folder provides the primary TypeScript and React frontend used by the app runtime.

## Current Scope

- Chat request and streaming response rendering through backend `/invocations`.
- Session commands:
  - `/token <databricks_access_token>`
  - `/clear-token`
  - `/persona <persona>`
  - `/clear-persona`
- Persona forwarding via `custom_inputs.persona`.
- Forwarded token header support (`x-forwarded-access-token` by default).
- Session status footer and source/tool hint footer.

## Run Locally

1. Install dependencies.

```bash
cd src/reactui
npm install
```

2. Configure environment.

```bash
cp .env.example .env
```

3. Start dev server.

```bash
npm run dev
```

## Build

```bash
npm run build
```

## Notes

- Default backend URL is `http://localhost:8000/invocations`.
- The React UI is served by the app runtime through `src/scripts/react_ui_server.py`.
- The legacy Chainlit implementation remains available under `src/frontend/` for fallback and compatibility checks.
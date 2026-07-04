# React UI (Parallel Frontend)

This folder provides a TypeScript and React frontend that runs in parallel with the existing Python frontend.

## Current Parity Scope

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
- The React UI is intentionally decoupled so you can run parity checks side-by-side with the existing frontend.
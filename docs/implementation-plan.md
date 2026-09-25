# Implementation plan — TechSignal

Build a runnable portfolio monorepo using React/TypeScript, FastAPI, SQLAlchemy,
Alembic, PostgreSQL and Plotly. Local SQLite mode provides a zero-infrastructure
preview; PostgreSQL is the deployment database. Every synthetic record is marked.
H1–H4 is a configurable technology horizon model.

## Phases and acceptance checks
1. Foundation: configuration, normalized models, migrations, JWT/RBAC, seed data.
   Validate migrations, seed counts, login and protected writes.
2. Ingestion: OpenAlex, GDELT, optional Semantic Scholar, EPO interface, responsible
   allowlisted scraper. Validate adapters against fixed provider fixtures.
3. Intelligence: transparent weighted scores, quantitative signals, approved
   horizons and assessment history. Validate formulas and approval boundaries.
4. AI: bounded retrieval, local embeddings, pgvector/FAISS retrieval, Gemini JSON
   schema, citation validation and deterministic no-key fallback. Test grounding.
5. Frontend: executive dashboard, Plotly radar, technology detail, evidence and
   charts, login, search/filter/navigation and responsive enterprise layout.
6. Organizations: editable sample startups, institution metrics and profiles.
7. Pipelines: durable run/step logs, staging, atomic merge, retry and scheduling.
   Test idempotence and injected failure rollback.
8. Reports: evidence-backed briefings, opportunity profiles, Markdown/PDF exports.
9. Verification: pytest, frontend tests/typecheck/build, Docker and GitHub Actions.
10. Deployment: Azure Container Apps guidance, security/operations notes and
    explicit record of verification limitations.

## Working rules
- Never use generated text as a factual source or silently approve AI horizons.
- Keep demo and live evidence separate, including score calculations and RAG.
- Only process bounded public API results and approved public web fragments.
- Persist pipeline diagnostics separately from the atomic evidence merge.
- No external credentials are required for demo mode; no secrets in source.
- Test meaningful failure paths and document unverified infrastructure honestly.

## Verification log — 2026-09-25

- Implemented all ten phases with documented deployment boundaries.
- 35 backend tests passed, including SSO RSA token validation, audience/nonce
  rejection, role mapping, one-time exchange/replay and expired-code handling.
- Ruff clean; SQLite migrations upgrade to head with no schema drift.
- PostgreSQL 16.15 + pgvector 0.8.6: fresh migrations (including SSO), seed,
  injected atomic rollback, successful merge and vector retrieval passed.
- Five frontend tests passed; TypeScript and Vite production build passed.
- Browser QA confirmed login, radar rendering, pinned sign out and return to login.
  Navigation has an independent scroll region; page changes reset content scroll.
- Live Gemini technology analysis and report generation succeeded. OpenAlex
  collected 14 live papers. GDELT was rate-limited (429); failures remain visible
  in pipeline logs. Public query results still require analyst relevance review.
- PDF export rendered and visually reviewed; synthetic assessments and live
  evidence are explicitly distinguished in report provenance.
- API keys moved into ignored local .env; .env.example contains placeholders only.
- Generated numeric claims must occur in evidence or verified metrics; violations,
  malformed output and provider failures now use a deterministic fallback.
- Microsoft SSO requires an Entra tenant registration before a real login can be
  exercised. Automated flow and cryptographic validation tests pass.
- Docker is absent locally; Compose builds/startup are configured in CI but have
  not been executed on this host. No Azure resources have been provisioned.
- Local preview uses SQLite. PostgreSQL is configured for Compose/deployment and
  was independently tested against an isolated local database.

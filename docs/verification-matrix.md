# Verification matrix

This matrix records the meaningful behavior checked before the portfolio release.
Automated tests use isolated databases and fixed provider responses; they do not
spend API quota or treat provider availability as correctness.

| Area | Cases exercised | Expected result |
|---|---|---|
| Authentication | Valid local login, missing token, role boundaries, Entra state/PKCE, RSA signature, nonce, audience, expired/replayed exchange | Authorized request succeeds; invalid or replayed identity data is rejected |
| Technology review | Valid evidence, foreign evidence, AI analysis ownership, H1–H4 move | Only linked evidence and explicit analyst review can change placement |
| Pipeline success | Collection, staging, validation, cleaning, deduplication, classification, entity linking, embedding, signals, grounding preparation, commit | Every displayed stage is successful and records are searchable |
| Pipeline failure | Invalid staged record, injected pre-commit failure, duplicate rerun, transient provider responses | Whole batch rejects or rolls back; diagnostics remain; rerun is idempotent; transient calls retry within budget |
| Data isolation | Synthetic and live modes, dataset switch | Queries, scores and retrieval never mix modes |
| AI grounding | Valid citations, invented citation, malformed schema, unsupported number, unavailable/invalid model response | Valid structured output persists; unsafe output falls back without fabricated numbers |
| Retrieval | Result bound, mode filter, incompatible embedding dimension, pgvector/FAISS fallback | Context remains bounded and retrieval remains available |
| Reports | Technology report, no-key fallback, ungrounded-model fallback, Markdown/PDF export | Briefing remains evidence-linked, labelled and exportable |
| Provider adapters | OpenAlex mapping, GDELT first-seen semantics, 429/5xx retry, SSRF/private address, robots denial, fragment extraction | Public data is normalized; unsafe or unavailable sources fail closed |
| Frontend | Search, filters, source labels, primary links, modal keyboard behavior, production build | Core analyst interactions work and TypeScript compiles |
| PostgreSQL | Fresh migration, pgvector extension, seed, rollback, merge, retrieval | Deployment database behavior matches application guarantees |

## External checks and limits

- Gemini structured generation was exercised with the configured local secret;
  secrets are excluded from Git. Runtime grounding can still choose the safe
  deterministic fallback when model output violates a rule.
- OpenAlex returned public records during live collection. Relevance still needs
  analyst review because search-provider inclusion does not prove relevance.
- GDELT returned HTTP 429 during the latest live check. Bounded retry and the
  no-mutation Deferred state are tested; the repository does not misstate provider uptime.
- GitHub Actions runs backend, frontend, PostgreSQL/pgvector and Compose jobs on
  every push. The Azure Container App and GitHub Pages frontend are deployed.

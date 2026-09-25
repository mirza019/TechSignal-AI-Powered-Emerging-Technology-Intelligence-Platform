# Trust model, score interpretation and operations

## H1–H4
The H1–H4 model is configurable for personal technology scouting workflows.
Defaults: H1 relatively mature (maturity ≥80), H2 increasing practical activity
(≥55), H3 promising but uncertain (≥30), H4 exploratory (≥0). Year labels are
illustrative portfolio settings, not predictions. Admins edit definitions and
thresholds. Existing placements change only through an authenticated analyst
review citing evidence from that technology and the active data mode.

## Quantitative indicators
See `app/analytics/scoring.py`; each score persists its formula, weights, metrics,
data mode and calculation time. Windows are rolling 365-day and preceding
365-day periods. Growth = (recent−prior)/max(prior,1). A zero prior baseline is
flagged; it is not a defensible percentage increase. Research/commercial volume
scores are demonstration heuristics, not measurements of technical feasibility.
Citation totals are available; citation acceleration is explicitly unmeasured
until multiple longitudinal snapshots exist. Source domains measure source
variety, not editorial independence. Maturity/relevance/confidence are analyst
inputs. Citation membership validation does not establish textual entailment.

## Isolation
Evidence, scores, AI records, organizations and reports carry synthetic flags.
RAG and dashboard metrics filter the active DEMO_MODE. Demo records must never
be represented as current public intelligence. Technology definitions can be
reused in live mode; their initial sample assessments remain visibly marked.
For real production use start an empty database and bootstrap an admin.

## Local security
Argon2 password hashes; signed expiring JWTs; database-checked user role; ORM-bound
queries; explicit CORS; rate limits for login, pipelines, LLMs and reports.
Tokens are sessionStorage-based for this local portfolio app: XSS could expose
one. No raw HTML is rendered from generated text. Use an identity provider and
secure cookies for a hardened public deployment. Local demo credentials are
published intentionally and prohibited by production startup settings.

Generated AI prose passes two grounding gates before persistence. Citation IDs
must belong to the exact retrieved bundle, and every numeric literal in generated
prose must already occur in the supplied evidence or verified computed metrics.
The application overwrites model confidence and horizon suggestions with
deterministic rules. Invalid JSON, timeouts, unsupported citations and unsupported
numbers produce a deterministic evidence summary so analyst work can continue.

## Scraping
Disabled by default. Exact hostname allowlist; HTTP(S) only on standard ports;
public IP resolution and IP-pinned requests prevent DNS rebinding; TLS verifies
the original host. Redirects and environment proxies are disabled. Robots checks
fail closed, including missing/unreachable robots. Identified user agent,
per-host spacing, robots crawl delay, 15-second read timeout, bounded retry,
1-MB response cap, bounded fragments, URL dedupe, depth 0 default/1 maximum.
Paywall/password markers are rejected. This cannot prove every site's terms
permit access: source approval must consider public restrictions. No full pages
are stored. JS-only pages return a clear error; optional Playwright rendering is
not shipped in v1 because it requires equally strict network interception.

## Pipeline durability
Collection is persisted into `staged_evidence`, then all data is validated.
A failed quality gate refuses the whole batch. Deduplication, entity linking,
embeddings, score changes and evidence merge run within one database transaction.
PostgreSQL merges use a transaction advisory lock. Step results and run failure
messages persist outside failed merge transactions. Successful stages report
aggregate work, not per-record profiling times. Retries replay the full bounded
run safely; completed records are matched by source ID/DOI/URL/hash/title.
Stage data retention should be configured operationally before long-term use.

## Known production gaps
Single-process scheduling, no distributed queue, Entra tenant configuration required, EPO
OPS placeholder, lightweight lexical vector encoder rather than a pretrained
semantic model, no independently validated commercial maturity, no automated
link-rot checking and no exhaustive claim-entailment verification. Organization
briefings use only explicitly linked evidence. Change review, security testing,
provider quota validation, backups and load testing remain deployment concerns.

# Azure Container Apps deployment

The portfolio deployment uses one Azure Container App with a public frontend and
an internal backend sidecar. Nginx proxies `/api` to the backend over localhost.
The GitHub workflow publishes both images to GitHub Container Registry.

Live API/app URL: [TechSignal on Azure](https://techsignal.icywater-653510cb.polandcentral.azurecontainerapps.io)

Public frontend: [TechSignal on GitHub Pages](https://mirza019.github.io/TechSignal-AI-Powered-Emerging-Technology-Intelligence-Platform/)

The hosted portfolio uses role-selected Microsoft SSO and persistent Azure Files-backed SQLite. The
Gemini key is stored as a Container
Apps secret and is referenced by the backend environment without appearing in the
manifest. The active revision is kept at one replica because pipeline tasks run in
the API process.

Deployment assets:

- `.github/workflows/publish-images.yml` builds immutable SHA-tagged frontend and
  backend images and publishes them to GHCR.
- `.azure/techsignal.containerapp.yaml` defines the two containers, ingress,
  resource limits, secret references and one-replica policy.
- `/health/ready` checks the backend database directly; `/api/auth/providers`,
  Microsoft SSO and the authenticated dashboard form the external smoke path.

The deployment is verified with role-selected SSO, dashboard reads, navigation/sign-out,
Gemini generation and the Microsoft Entra authorization redirect. GitHub Pages
uses `VITE_API_BASE` to call the Azure API and `HashRouter` for static-host routes.

## Full production deployment

1. Provision Azure Database for PostgreSQL Flexible Server and a database `radar`.
   Require TLS (`?sslmode=require` on DATABASE_URL). Use private networking or an
   explicitly restricted firewall. Allow the `vector` extension if available.
   FAISS works when extension installation is unavailable.
2. Build both images from the repository root with the supplied Dockerfiles and
   push them to an Azure Container Registry. Use managed identity for image pulls.
3. Create a Container Apps environment. Deploy backend with internal ingress on
   port 8000. Use one replica and one worker while APScheduler and the in-process
   limiter are used. Set min replicas to 1 if scheduled jobs are enabled.
4. Store DATABASE_URL, GEMINI_API_KEY and APP_SECRET in Container Apps secrets or
   Key Vault references, never ordinary committed files. APP_SECRET must be a
   cryptographically random value of at least 32 characters.
5. Set ENVIRONMENT=production, DEMO_MODE=false, SEED_DEMO=false, explicit
   CORS_ORIGINS JSON, and the provider flags. Configure an identifying scraper
   contact and exact allowlist. Only enable APIs you intend to use.
6. Run `alembic upgrade head` as a deployment job before serving the new revision.
   Run `python -m app.cli bootstrap-admin` once in a secure container console.
   Add technologies through the authenticated API/UI. Do not use demo credentials.
7. Deploy the frontend with external HTTPS ingress on port 8080. Replace nginx's
   `http://backend:8000` upstream with the backend's internal Container Apps FQDN,
   including its HTTPS scheme and appropriate Host/SNI configuration. Alternatively
   put both containers in one app revision and proxy to `http://127.0.0.1:8000`.
8. Readiness: GET /health/ready. Liveness: GET /health. Frontend health: GET /.
   Use Log Analytics for logs, metrics and alerts; avoid logging source fragments,
   prompts or credential-bearing URLs. Back up PostgreSQL before migrations.
9. Verify authentication, Viewer write rejection, real provider limits, citations,
   report exports, rollback, redirects/SSRF and a complete collection run against
   a staging deployment before production use. Configure egress restrictions.

## Scaling and identity roadmap
Replace BackgroundTasks/APScheduler with Celery + Redis and an isolated scheduler
before increasing replicas. Use a shared Redis or gateway rate limiter. Configure
the implemented Microsoft Entra authorization-code flow using [SSO setup](sso-setup.md).
Set FRONTEND_URL and ENTRA_REDIRECT_URI to the deployed HTTPS origin.
Use short sessions and HttpOnly cookies if public browser deployment requires it.
A task queue is also required for durable crash-resumable work. The current server
marks interrupted runs failed on restart and supports an explicit safe retry.

## Deployment workflow outline
GitHub Actions CI builds and validates both images. An Azure deployment workflow
should authenticate using GitHub OIDC, push immutable SHA-tagged images, run the
migration job, update revisions, check readiness and promote traffic. Configure
Azure tenant/subscription/client IDs and federated credentials in repository
settings. No workflow here silently provisions or charges an Azure subscription.

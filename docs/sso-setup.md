# Microsoft Entra single sign-on

The application implements a single-tenant authorization-code flow with PKCE.
Local workspace login remains available. Sign out clears this application's session;
it does not sign the user out of Microsoft or other Microsoft applications.

1. In your Microsoft Entra tenant, register a single-tenant application.
2. Add a **Web** redirect URI matching the browser origin exactly:
   `http://127.0.0.1:5173/api/auth/sso/callback` for local Vite development,
   `http://localhost:8080/api/auth/sso/callback` for Compose, or your HTTPS production URL.
3. Create a client secret and put its **value** in the ignored `.env` file. Never put
   real secrets in `.env.example`. Set `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`,
   `ENTRA_CLIENT_SECRET`, `ENTRA_REDIRECT_URI` and `FRONTEND_URL`.
4. Optionally restrict email domains with `ENTRA_ALLOWED_DOMAINS=["example.com"]`.
   Configure user assignment in the enterprise application to limit tenant access.
5. Define app roles with values `Radar.Admin`, `Radar.Analyst`, and `Radar.Viewer`,
   and assign users/groups. Unassigned authenticated users receive Viewer.
6. Restart the backend. The Microsoft button becomes enabled automatically.

Production requires HTTPS URLs, a random APP_SECRET of at least 32 characters,
SEED_DEMO=false and DEMO_MODE=false. Store the client secret in your deployment
secret manager. Disable access-log query strings on the authentication callback.

The server checks state, nonce, tenant, RS256 signature, issuer, audience and token
expiry. The PKCE verifier is held in a signed HttpOnly, SameSite=Lax cookie; in
production it is Secure. The return URL contains only a random 60-second one-time
exchange code. The application token is stored in sessionStorage. Existing local
accounts are never automatically linked by matching email; use a distinct account
or implement an administrator-reviewed identity-linking workflow.

Automated tests verify PKCE/state, failure handling, role mapping, valid RSA
signatures, audience/nonce rejection, exchange expiry and replay rejection. A real
tenant login still requires your organization's app registration and credentials.

References: [Microsoft authorization-code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
and [OpenID Connect](https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc).

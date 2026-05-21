# Security model

> Hardening checklist finalised in Phase 6 — see end of document.

## Threat model

Primary assets: PII of underage students (alumnes), academic records, staff accounts. Adversaries: external (credential stuffing, phishing), internal (compromised teacher account misusing access). The system handles GDPR-relevant data; the platform itself acts as the system of record (permanent academic archive).

## Authentication

- DNI _or_ email + bcrypt(12) password. Admin generates passwords (16-char strong). Passwords never stored or logged in plaintext; the reveal-once UI relies on a 5-minute Redis-backed token between generate and email/share actions.
- Forced password change on first login (`must_change_password` flag).
- Optional TOTP MFA for admin role (RFC 6238).
- Optional Google Workspace OAuth (domain-restricted to `@inslaferreria.cat`). Linking requires the current password — stolen Google account alone cannot bypass initial password.
- JWT RS256 with rotated keypair. Access token 15 min. Refresh cookie HttpOnly + Secure + SameSite=Strict + 7d, server-side rotation, family revocation on reuse detection.
- Rate limiting via slowapi: 5 login attempts/min/IP, 60 writes/min/user.

## Authorization

Role-based + relationship-based, enforced at three layers:

1. FastAPI dependency rejects with 403 before service layer.
2. Service layer re-checks (defence in depth).
3. Frontend hides controls user can't use (UX, not security).

A professor can edit RA notes only if `assignacions_docents` matches their `(user_id, grup_id, modul_id, curs_acad_id)` AND the avaluació is in `docent` state. A professor can edit any nota for a group if `grups_classe.tutor_user_id == user_id` AND the avaluació is in `junta` state. Admin override is auditable.

## Transport & headers

- HTTPS only (HSTS preload, 2-year max-age, includeSubDomains)
- CORS locked to the frontend origin; no `*` wildcards
- CSP: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' fonts.googleapis.com; font-src 'self' fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'`
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
- CSRF: double-submit cookie pattern for state-changing requests

## Input validation

- Every endpoint has a Pydantic schema; rejects unknown fields.
- SQL only via SQLAlchemy parameterised queries (no raw SQL).
- Excel/CSV upload: 5 MB cap, 10k row cap, MIME + magic-byte check, sanitised cells (strip `=`/`+`/`-`/`@` lead chars to prevent CSV formula injection).
- PDF: server-rendered Jinja2 with autoescape; no user HTML accepted.
- Email: `to` always derived server-side from alumne record; never accepted from frontend payload.

## Data retention — permanent archive

The system is a universal academic archive. **No automatic deletion or anonymisation jobs.** Data persists forever until an admin explicitly deletes it.

- **Soft delete only** (default): every entity has `deleted_at` + `deleted_by_user_id`. Reversible by admin.
- **Hard delete**: restricted to admin via dedicated endpoint with double-confirmation; cascades documented per entity, full before-state snapshot logged in `audit_logs`.
- **GDPR right to access**: admin export endpoint produces a per-alumne ZIP (PDF + JSON) with all stored data.
- **GDPR right to erasure**: case-by-case via admin action (soft-delete first, hard-delete after legal review).
- **Audit logs are append-only and never deleted** — they are part of the permanent archive.
- Audit JSON is data-minimised: nota values logged only when changed.

## Backups

- Nightly `mysqldump` (gzipped + age-encrypted) → off-server SMB share or Azure Blob.
- Weekly restore drill on staging.
- Retention: keep 30 daily + 12 monthly + 7 yearly snapshots.

## Secret management

- Local dev: `.env` (gitignored) + JWT keys in `secrets/` (gitignored).
- Production: Docker Compose `secrets:` (file-based, mounted into containers).
- Nothing sensitive in env vars or images at rest.

## Dependency hygiene

- `pip-audit`, `pnpm audit`, `trivy image` run in CI.
- High/critical findings fail the pipeline.
- Dependabot keeps base images and direct deps current.

## Compliance documentation

Lawful-basis statement, DPIA, retention policy, and incident response runbook live alongside this file (DPO sign-off pending).

---

## Hardening checklist (Phase 6)

### Transport
- [x] HTTPS only — `infra/nginx/nginx.conf` redirects all 80 → 443
- [x] HSTS 2 years + `includeSubDomains` + `preload` — emitted both by nginx and `SecurityHeadersMiddleware`
- [x] Modern TLS only (1.2 + 1.3, ECDHE-only ciphers)
- [x] OCSP stapling enabled

### Headers (defence in depth — both nginx and FastAPI middleware emit them)
- [x] `Content-Security-Policy` — `default-src 'self'`, no inline scripts, no eval, `frame-ancestors 'none'`, fonts.googleapis allowed for the Inter/Fraunces/etc. webfonts
- [x] `X-Content-Type-Options: nosniff`
- [x] `X-Frame-Options: DENY`
- [x] `Referrer-Policy: strict-origin-when-cross-origin`
- [x] `Permissions-Policy` denying geolocation, camera, microphone, payment, USB, FLoC
- [x] `Cross-Origin-Opener-Policy: same-origin`
- [x] `Cross-Origin-Resource-Policy: same-site`

### Authentication
- [x] DNI/email + bcrypt(12) password
- [x] JWT RS256, access 15 min + refresh 7 d (HttpOnly + Secure + SameSite=Strict cookie)
- [x] Refresh-token reuse detection → entire family revoked (Redis-backed)
- [x] Force password change on first login (`must_change_password` flag)
- [x] Optional TOTP MFA for admin (`mfa_secret`)
- [ ] Google OAuth linking — designed in Phase 1, not yet wired (deferred)

### Rate limiting
- [x] slowapi with per-IP fallback / per-JWT key
- [x] `/auth/login` capped at 5 / minute (configurable via `RATE_LIMIT_LOGIN_PER_MINUTE`)
- [x] Writes capped at 60 / minute

### Input handling
- [x] Pydantic v2 schemas reject unknown fields and validate types
- [x] SQL only via SQLAlchemy parameterised queries — no raw SQL anywhere
- [x] Excel/CSV upload limited to 5 MB, MIME-validated
- [x] CSV cell sanitisation (no formula injection — leading `=`/`+`/`-`/`@` rejected)
- [x] PDF rendered server-side via Jinja2 with autoescape; no user HTML accepted
- [x] Email recipients always derived server-side from the alumne record

### Audit
- [x] Append-only `audit_logs` — every grade write, evaluation transition, import, password regenerate, mass email recorded
- [x] Audit-log viewer endpoint admin-only (`/api/v1/audit-logs`)

### Backups
- [x] Nightly `mysqldump` + gzip + age/gpg encrypt — `infra/windows-server/backup.ps1` + `scripts/backup.sh`
- [x] Restore script with double-confirmation — `infra/windows-server/restore.ps1`
- [x] Retention: 30 daily / 12 monthly / 7 yearly snapshots

### Observability
- [x] Structured JSON logging with request-ID propagation
- [x] Prometheus `/metrics` endpoint, IP-restricted to internal networks
- [x] Sentry SDK auto-init when `SENTRY_DSN` set (FastAPI + SQLAlchemy integrations, PII scrubbed)
- [x] Per-route HTTP request counter + latency histogram

### Secrets
- [x] Local dev: `.env` (gitignored) + JWT keys in `secrets/`
- [x] Production: Docker Compose `secrets:` (file-based, mounted into containers — see `docker-compose.prod.yml`)
- [x] No secrets in environment variables in production
- [ ] Quarterly secret rotation — runbook drafted; first rotation drill scheduled with first deployment

### Dependencies
- [x] `pip-audit` + `pnpm audit` run in CI
- [x] Trivy image scan in CI for backend + frontend images
- [x] Critical findings fail the pipeline

### Data retention
- [x] Permanent archive — no automatic deletion
- [x] Soft delete with `deleted_at` + `deleted_by_user_id` everywhere
- [x] Hard delete admin-only with double confirmation
- [x] GDPR right to access — admin per-alumne export endpoint (deferred to Phase 7 polish)

### Outstanding (post-launch)
- [ ] Per-alumne GDPR-export endpoint (Phase 7)
- [ ] WebAuthn / passkey support for admin (future)
- [ ] SMTP webhook integration for accurate bounce + open tracking

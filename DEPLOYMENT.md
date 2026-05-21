# Deployment

Production runs on Windows Server via Docker Compose. The complete runbook is
in [`infra/windows-server/README.md`](./infra/windows-server/README.md). This
document is the high-level overview.

## Target

Windows Server 2019 / 2022, on-premise at Institut la Ferreria, exposed at
`https://arxiu.inslaferreria.cat`.

## Provisioning at a glance

```powershell
# As Administrator
git clone https://github.com/<org>/arxiu-prod.git C:\arxiu
cd C:\arxiu
.\infra\windows-server\install.ps1 -Domain arxiu.inslaferreria.cat

# Edit C:\arxiu\.env.production — fill SMTP + (optional) Google OAuth

Start-Service ArxiuStack
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml `
  --env-file .env.production exec backend alembic upgrade head
```

Browse https://arxiu.inslaferreria.cat.

## What the bootstrap does

| Step | Outcome |
|---|---|
| Check Docker | refuses if Docker isn't running |
| `C:\arxiu\{backups,secrets,logs,storage}` | created |
| `secrets\mysql_*_password`, `secrets\jwt_{private,public}.pem` | generated (idempotent — never overwrites) |
| `.env.production` | written with the generated MySQL passwords; SMTP/OAuth left empty |
| Docker images | built |
| Windows Firewall | 80 + 443 allowed inbound; 3306 + 6379 blocked |
| `ArxiuStack` Windows Service | NSSM-wrapped Docker Compose, `SERVICE_AUTO_START` |
| `ArxiuBackup` scheduled task | runs `backup.ps1` at 03:00 daily |

## TLS

Three options — see the runbook §3:

1. **Let's Encrypt** via the certbot container (auto-renews every 12 h)
2. **Institutional CA** wildcard cert mounted into nginx
3. **Self-signed** for staging

## Operations

| Task | Command |
|---|---|
| Restart stack | `Restart-Service ArxiuStack` |
| Logs | `docker compose ... logs -f backend` |
| Manual backup | `.\infra\windows-server\backup.ps1` |
| Restore | `.\infra\windows-server\restore.ps1 -BackupFile <path>` |
| Migration | `docker compose ... exec backend alembic upgrade head` |
| Audit log query | `/audit-logs` page in the app, or direct SQL |

## Disaster recovery

- Container crash → NSSM auto-restart, RTO ~1 min
- MySQL corruption → restore latest nightly, RTO ~30 min
- Complete host loss → new VM + `install.ps1` + secrets restore + backup restore, RTO ~2 h

Backups: 30 daily, gzipped + GPG-encrypted, off-site copy via shared drive or
Azure Blob (set up separately).

## Monitoring

- `/healthz` — Docker healthcheck
- `/metrics` — Prometheus, IP-restricted to internal networks
- Sentry when `SENTRY_DSN` is set
- Structured JSON logs with request-ID correlation, captured by Docker's
  `json-file` driver (size-capped, rotated)

## Updates

```powershell
cd C:\arxiu
git fetch && git checkout v1.x.y
docker compose ... build
Restart-Service ArxiuStack
docker compose ... exec backend alembic upgrade head
```

For air-gapped environments, ship Docker images as tarballs and `docker load`
on the target.

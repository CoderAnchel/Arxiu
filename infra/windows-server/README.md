# Windows Server deployment runbook

Complete first-deployment + ongoing-operations guide for the Arxiu production
stack on Windows Server 2019 or 2022.

## 1. Server prerequisites

| Resource | Recommended |
|---|---|
| OS | Windows Server 2019 / 2022 (with WSL 2 enabled) |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Disk | 80 GB (DB + uploads + backups) |
| Network | Static IP, DNS A-record, ports 80 + 443 inbound |

Software to install before running `install.ps1`:

1. **Docker Desktop for Windows** with WSL 2 backend, OR
   [Mirantis Container Runtime for Windows](https://docs.mirantis.com/mcr/25.0/install/mcr-windows.html)
2. **OpenSSL for Windows** (Win32/Win64 build from [slproweb](https://slproweb.com/products/Win32OpenSSL.html))
3. **NSSM** — extract `nssm.exe` to `C:\Tools\nssm\` (or pass `-NssmPath`)
4. **GnuPG for Windows** (optional but recommended — used to encrypt backups)
5. **Git for Windows** (to clone the repository)

## 2. Initial install

```powershell
# 1. Clone the repo to C:\arxiu
git clone https://github.com/<org>/arxiu-prod.git C:\arxiu

# 2. Run the bootstrap (Administrator PowerShell)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd C:\arxiu
.\infra\windows-server\install.ps1 -Domain arxiu.inslaferreria.cat
```

The script:

- Verifies Docker, creates `C:\arxiu\{backups,secrets,logs,storage}`
- Generates a 2048-bit RSA JWT keypair + random MySQL passwords (idempotent)
- Writes `.env.production` (review and fill SMTP + OAuth before starting)
- Builds the Docker images
- Configures the Windows Firewall
- Registers an `ArxiuStack` Windows Service (NSSM-wrapped `docker compose up`)
- Schedules the `ArxiuBackup` task at 03:00 daily

## 3. TLS certificate

Three supported options:

### Option A — Let's Encrypt (HTTP-01 via certbot container)
The production compose already includes a certbot container that polls every
12 h. First-time issuance:

```powershell
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml `
  --env-file .env.production run --rm certbot `
  certonly --webroot -w /var/www/certbot -d arxiu.inslaferreria.cat `
  --email tic@inslaferreria.cat --agree-tos --no-eff-email
```

### Option B — Institutional CA wildcard cert
Place `fullchain.pem` and `privkey.pem` in
`C:\arxiu\secrets\institutional\` and bind-mount them into the nginx container
by adding to `docker-compose.prod.yml`:

```yaml
volumes:
  - ./secrets/institutional:/etc/letsencrypt/live/arxiu:ro
```

### Option C — Self-signed (staging only)
```powershell
openssl req -x509 -newkey rsa:2048 -keyout secrets\institutional\privkey.pem `
  -out secrets\institutional\fullchain.pem -days 365 -nodes `
  -subj "/CN=arxiu.inslaferreria.cat"
```

## 4. First start

```powershell
Start-Service ArxiuStack

# Wait ~30s for MySQL to become healthy, then:
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml `
  --env-file .env.production exec backend alembic upgrade head

docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml `
  --env-file .env.production exec backend python -m app.scripts.seed_admin
# ↑ prints the initial admin password ONCE — capture it from the logs
```

Browse https://arxiu.inslaferreria.cat — log in with DNI `00000000T` and the
captured password. You will be forced to change it on first login.

## 5. Day-to-day operations

| Task | Command |
|---|---|
| View logs | `docker compose ... logs -f --tail=100 backend` |
| Restart stack | `Restart-Service ArxiuStack` |
| Apply migration after upgrade | `docker compose ... exec backend alembic upgrade head` |
| Manual backup | `.\infra\windows-server\backup.ps1` |
| Restore | `.\infra\windows-server\restore.ps1 -BackupFile <path>` |
| Audit log query | Use the in-app `/audit-logs` viewer or `mysql ... -e 'SELECT ...'` |

## 6. Backups

- Nightly at 03:00 via `ArxiuBackup` Task Scheduler entry
- Output: `C:\arxiu\backups\arxiu-YYYYMMDD-HHMMSS.sql.gz[.gpg]`
- GPG encryption activates when `ARXIU_BACKUP_GPG_KEY_ID` env-var is set on
  the SYSTEM scheduler context (recommended)
- Retention: 30 daily snapshots
- **Verify monthly**: copy the latest backup to a staging Windows Server and
  run `restore.ps1` against an empty DB. Confirm `make test-backend` still
  passes against the restored data.

## 7. Updates / redeployment

```powershell
cd C:\arxiu
git fetch && git checkout v1.x.y          # tag the release first

docker compose ... build
Restart-Service ArxiuStack
docker compose ... exec backend alembic upgrade head
```

CI builds + tags images on each release; in air-gapped deployments, copy the
tagged tarballs and `docker load` them.

## 8. Disaster recovery

| Scenario | RTO | Procedure |
|---|---|---|
| Container crash | 1 min | NSSM auto-restart |
| Host reboot | 3 min | NSSM SERVICE_AUTO_START |
| MySQL volume corruption | 30 min | Restore the latest nightly backup via `restore.ps1`, then `alembic upgrade head` |
| Complete host loss | 2 h | Provision a new Windows Server, run `install.ps1`, copy `secrets\` from a secure off-site location, restore the latest backup |

## 9. Monitoring

- `/healthz` — Docker healthcheck (rolls into `docker compose ps`)
- `/metrics` — Prometheus scrape endpoint (IP-restricted to internal networks)
- **Sentry** — set `SENTRY_DSN` in `.env.production` to capture exceptions
- **Logs** — JSON to stdout, captured by Docker's `json-file` driver, with
  size limits (`max-size=100m`, `max-file=3`) configured in the prod compose

## 10. Removing the install

```powershell
Stop-Service ArxiuStack
sc.exe delete ArxiuStack
Unregister-ScheduledTask -TaskName "ArxiuBackup" -Confirm:$false

docker compose ... down -v       # volumes!
Remove-Item C:\arxiu -Recurse -Force
```

Backups in off-site storage are intentionally NOT deleted.

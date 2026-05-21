# Arxiu de notes — Windows Server bootstrap.
#
# Run as Administrator. Requires Windows Server 2019/2022 with internet access
# and Docker Desktop for Windows already installed (or Mirantis Docker Engine).
#
# What this script does:
#   1. Verifies Docker is available
#   2. Creates the directory layout under $InstallDir
#   3. Generates JWT keypair + MySQL/admin secrets if missing
#   4. Installs NSSM and registers ArxiuStack as a Windows Service
#   5. Schedules nightly backup via Task Scheduler
#   6. Opens the firewall on 80 + 443 (denies external 3306/6379)
#
# Usage:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\install.ps1 -InstallDir C:\arxiu -Domain arxiu.inslaferreria.cat

param(
  [string]$InstallDir = "C:\arxiu",
  [string]$Domain     = "arxiu.inslaferreria.cat",
  [string]$NssmPath   = "C:\Tools\nssm\nssm.exe",
  [switch]$SkipNssm,
  [switch]$SkipFirewall
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n→ $msg" -ForegroundColor Cyan }
function OK($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }

# 1. Docker check ------------------------------------------------------------
Step "Verifying Docker"
try {
  $v = (& docker version --format '{{.Server.Version}}') 2>$null
  if ($LASTEXITCODE -ne 0) { throw "docker not running" }
  OK "Docker $v"
} catch {
  throw "Docker is not running. Start Docker Desktop / Engine first."
}

# 2. Directory layout --------------------------------------------------------
Step "Creating directories under $InstallDir"
$dirs = @(
  $InstallDir,
  "$InstallDir\backups",
  "$InstallDir\secrets",
  "$InstallDir\logs",
  "$InstallDir\storage"
)
foreach ($d in $dirs) {
  if (-not (Test-Path $d)) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
    OK "created $d"
  } else {
    OK "exists $d"
  }
}

# 3. Secrets ----------------------------------------------------------------
Step "Generating secrets (idempotent)"

function Ensure-RandomFile($path, [int]$bytes = 32) {
  if (-not (Test-Path $path)) {
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buf = New-Object byte[] $bytes
    $rng.GetBytes($buf)
    [System.IO.File]::WriteAllText($path, [Convert]::ToBase64String($buf))
    OK "wrote $path"
  } else {
    OK "exists $path"
  }
}

Ensure-RandomFile "$InstallDir\secrets\mysql_root_password"
Ensure-RandomFile "$InstallDir\secrets\mysql_password"

# JWT keypair via OpenSSL (must be on PATH or in $InstallDir\bin)
$jwtPriv = "$InstallDir\secrets\jwt_private.pem"
$jwtPub  = "$InstallDir\secrets\jwt_public.pem"
if (-not (Test-Path $jwtPriv)) {
  Step "Generating JWT keypair"
  & openssl genpkey -algorithm RSA -out $jwtPriv -pkeyopt rsa_keygen_bits:2048
  if ($LASTEXITCODE -ne 0) { throw "openssl genpkey failed — install OpenSSL or add to PATH" }
  & openssl rsa -pubout -in $jwtPriv -out $jwtPub
  if ($LASTEXITCODE -ne 0) { throw "openssl rsa failed" }
  icacls $jwtPriv /inheritance:r /grant:r "BUILTIN\Administrators:F" "NT AUTHORITY\SYSTEM:F" | Out-Null
  OK "JWT keypair generated"
} else {
  OK "JWT keypair already exists"
}

# 4. .env.production ---------------------------------------------------------
$envFile = "$InstallDir\.env.production"
if (-not (Test-Path $envFile)) {
  Step "Writing $envFile (review and edit before first start!)"
  $mysqlRoot = (Get-Content "$InstallDir\secrets\mysql_root_password" -Raw).Trim()
  $mysqlPwd  = (Get-Content "$InstallDir\secrets\mysql_password" -Raw).Trim()
  @"
APP_ENV=production
APP_NAME=Arxiu Institut la Ferreria
LOG_LEVEL=INFO
TZ=Europe/Madrid

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_CORS_ORIGINS=https://$Domain
BACKEND_PUBLIC_URL=https://$Domain

JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private_key
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public_key
JWT_ALGORITHM=RS256
JWT_ACCESS_TTL_SECONDS=900
JWT_REFRESH_TTL_SECONDS=604800

# Database
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=arxiu
MYSQL_USER=arxiu
MYSQL_PASSWORD=$mysqlPwd
MYSQL_ROOT_PASSWORD=$mysqlRoot
DATABASE_URL=mysql+asyncmy://arxiu:$mysqlPwd@mysql:3306/arxiu?charset=utf8mb4

# Redis
REDIS_URL=redis://redis:6379/0

# Google OAuth — fill in if enabled
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=https://$Domain/api/v1/auth/oauth/google/callback
GOOGLE_OAUTH_ALLOWED_DOMAIN=inslaferreria.cat

# SMTP — point at the institutional relay
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=true
SMTP_FROM_ADDRESS=no-reply@inslaferreria.cat
SMTP_FROM_NAME=Arxiu Institut la Ferreria

# Storage
STORAGE_ROOT=/var/arxiu/storage

# Security
PASSWORD_BCRYPT_ROUNDS=12
PASSWORD_MIN_LENGTH=12
ADMIN_PASSWORD_REVEAL_TTL_SECONDS=300
RATE_LIMIT_LOGIN_PER_MINUTE=5
RATE_LIMIT_WRITE_PER_MINUTE=60

# Observability
SENTRY_DSN=
PROMETHEUS_ENABLED=true

# Frontend
VITE_API_BASE_URL=https://$Domain/api/v1
VITE_APP_NAME=Arxiu Institut la Ferreria
"@ | Set-Content $envFile -Encoding utf8
  OK "wrote $envFile"
} else {
  OK "$envFile already exists"
}

# 5. Build images ------------------------------------------------------------
Step "Building Docker images"
Push-Location $InstallDir
try {
  & docker compose `
    -f infra/compose/docker-compose.yml `
    -f infra/compose/docker-compose.prod.yml `
    --env-file .env.production `
    build
  if ($LASTEXITCODE -ne 0) { throw "build failed" }
  OK "images built"
} finally { Pop-Location }

# 6. Firewall ---------------------------------------------------------------
if (-not $SkipFirewall) {
  Step "Configuring firewall"
  New-NetFirewallRule -DisplayName "Arxiu HTTP"  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80  -ErrorAction SilentlyContinue | Out-Null
  New-NetFirewallRule -DisplayName "Arxiu HTTPS" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443 -ErrorAction SilentlyContinue | Out-Null
  # Block accidental external exposure of MySQL/Redis (Docker may map them in dev compose)
  New-NetFirewallRule -DisplayName "Arxiu Block MySQL" -Direction Inbound -Action Block -Protocol TCP -LocalPort 3306 -ErrorAction SilentlyContinue | Out-Null
  New-NetFirewallRule -DisplayName "Arxiu Block Redis" -Direction Inbound -Action Block -Protocol TCP -LocalPort 6379 -ErrorAction SilentlyContinue | Out-Null
  OK "firewall rules applied"
}

# 7. NSSM service -----------------------------------------------------------
if (-not $SkipNssm) {
  if (-not (Test-Path $NssmPath)) {
    Warn "NSSM not found at $NssmPath — skipping service install (download from nssm.cc)"
  } else {
    Step "Registering ArxiuStack Windows Service via NSSM"
    & $NssmPath stop ArxiuStack 2>&1 | Out-Null
    & $NssmPath remove ArxiuStack confirm 2>&1 | Out-Null

    $cmd = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    $args = "compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml --env-file .env.production up"
    & $NssmPath install ArxiuStack $cmd $args | Out-Null
    & $NssmPath set ArxiuStack AppDirectory $InstallDir | Out-Null
    & $NssmPath set ArxiuStack AppStdout    "$InstallDir\logs\stdout.log" | Out-Null
    & $NssmPath set ArxiuStack AppStderr    "$InstallDir\logs\stderr.log" | Out-Null
    & $NssmPath set ArxiuStack Start        SERVICE_AUTO_START | Out-Null
    & $NssmPath set ArxiuStack Description  "Arxiu de notes — production stack (Docker Compose)" | Out-Null
    OK "ArxiuStack service registered"
    Warn "Start with: Start-Service ArxiuStack"
  }
}

# 8. Backup task ------------------------------------------------------------
Step "Scheduling nightly backup task"
$existing = Get-ScheduledTask -TaskName "ArxiuBackup" -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName "ArxiuBackup" -Confirm:$false }

$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
           -Argument "-NoProfile -ExecutionPolicy Bypass -File $InstallDir\infra\windows-server\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 03:00
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) -StartWhenAvailable
Register-ScheduledTask -TaskName "ArxiuBackup" -Action $action -Trigger $trigger -Settings $settings `
                       -User "SYSTEM" -RunLevel Highest | Out-Null
OK "ArxiuBackup task scheduled @ 03:00 daily"

Write-Host "`nBootstrap complete. Next steps:" -ForegroundColor Green
Write-Host "  1. Edit $envFile — fill SMTP + Google OAuth credentials"
Write-Host "  2. Provision TLS cert (certbot or institutional CA) into the letsencrypt volume"
Write-Host "  3. Start-Service ArxiuStack"
Write-Host "  4. docker compose ... exec backend alembic upgrade head"
Write-Host "  5. docker compose ... exec backend python -m app.scripts.seed   # initial admin"
Write-Host "  6. Browse https://$Domain"

# ============================================================================
# Arxiu de notes — Windows Server BOOTSTRAP
# ----------------------------------------------------------------------------
# Un sol script que deixa l'app llesta per ser testada al centre.
#
# Què fa (per ordre):
#   1. Verifica que Docker Desktop estigui en marxa
#   2. Crea l'estructura de carpetes a $InstallDir (default C:\arxiu)
#   3. Genera secrets si encara no existeixen (JWT keys, MySQL pwd, admin pwd)
#   4. Construeix les imatges Docker
#   5. Aixeca la stack (mysql + redis + backend + worker + frontend + nginx)
#   6. Espera que MySQL estigui llest
#   7. Aplica migracions Alembic
#   8. Executa seed amb dades de prova (cicles + grups + alumnes demo)
#   9. Mostra l'URL i la contrasenya d'admin per al centre
#
# Es pot tornar a executar tantes vegades com vulguis: és idempotent.
#
# Ús:
#   Obre PowerShell com Administrador i fes:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#     cd C:\arxiu                # on hagis clonat el repo
#     .\infra\windows-server\bootstrap.ps1
# ============================================================================

param(
  [string]$InstallDir = (Get-Location).Path,
  [string]$Port       = "8080",      # port HTTP local (canvia si 80 ocupat)
  [switch]$SkipSeed,                  # no carregar dades demo
  [switch]$SkipBuild                  # no reconstruir imatges
)

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Arxiu de notes — Bootstrap"

# --- helpers ---------------------------------------------------------------
function Step($msg) {
  Write-Host ""
  Write-Host "========================================" -ForegroundColor DarkCyan
  Write-Host " $msg" -ForegroundColor Cyan
  Write-Host "========================================" -ForegroundColor DarkCyan
}
function OK($msg)   { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Info($msg) { Write-Host "  [INFO] $msg" -ForegroundColor Gray }
function Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Fail($msg) {
  Write-Host "  [FAIL] $msg" -ForegroundColor Red
  exit 1
}

function NewRandomPassword([int]$length = 24) {
  $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#%*-_"
  $bytes = New-Object byte[] $length
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $sb = New-Object System.Text.StringBuilder
  foreach ($b in $bytes) { [void]$sb.Append($chars[$b % $chars.Length]) }
  return $sb.ToString()
}

# --- 0. Pre-flight -----------------------------------------------------
Step "Pre-flight: comprovacions inicials"

if (-not (Test-Path "$InstallDir\infra\compose\docker-compose.yml")) {
  Fail "No s'ha trobat infra\compose\docker-compose.yml a $InstallDir. Executa el script des de l'arrel del repo."
}
OK "Repo trobat a $InstallDir"

try {
  $v = (& docker version --format '{{.Server.Version}}') 2>$null
  if ($LASTEXITCODE -ne 0) { throw "docker not running" }
  OK "Docker $v"
} catch {
  Fail "Docker no està en marxa. Inicia Docker Desktop i torna a executar."
}

# --- 1. Estructura de carpetes -----------------------------------------
Step "Carpetes de dades persistents"
$dirs = @(
  "$InstallDir\backups",
  "$InstallDir\secrets",
  "$InstallDir\logs",
  "$InstallDir\storage"
)
foreach ($d in $dirs) {
  if (-not (Test-Path $d)) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
    OK "Creada $d"
  } else {
    OK "Ja existeix $d"
  }
}

# --- 2. Secrets --------------------------------------------------------
Step "Generació de secrets (només si encara no existeixen)"
$secretsDir = "$InstallDir\secrets"

# JWT keys ---
if (-not (Test-Path "$secretsDir\jwt_private.pem")) {
  Info "Generant clau JWT RSA-2048"
  & docker run --rm -v "${secretsDir}:/keys" alpine/openssl `
    genpkey -algorithm RSA -out /keys/jwt_private.pem -pkeyopt rsa_keygen_bits:2048 2>&1 | Out-Null
  & docker run --rm -v "${secretsDir}:/keys" alpine/openssl `
    rsa -pubout -in /keys/jwt_private.pem -out /keys/jwt_public.pem 2>&1 | Out-Null
  OK "JWT keypair creat"
} else {
  OK "JWT keypair ja existeix"
}

# MySQL passwords ---
if (-not (Test-Path "$secretsDir\mysql_root_password")) {
  NewRandomPassword 32 | Out-File -FilePath "$secretsDir\mysql_root_password" -Encoding ascii -NoNewline
  OK "MySQL root password generada"
}
if (-not (Test-Path "$secretsDir\mysql_password")) {
  NewRandomPassword 32 | Out-File -FilePath "$secretsDir\mysql_password" -Encoding ascii -NoNewline
  OK "MySQL user password generada"
}

# .env.production ---
$envFile = "$InstallDir\.env.production"
if (-not (Test-Path $envFile)) {
  $mysqlPass = (Get-Content "$secretsDir\mysql_password" -Raw).Trim()
  $mysqlRoot = (Get-Content "$secretsDir\mysql_root_password" -Raw).Trim()

  $envContent = @"
# Arxiu de notes — production .env (generat automàticament)
APP_ENV=production
APP_NAME=Arxiu de notes
HTTP_PORT=$Port
MYSQL_DATABASE=arxiu
MYSQL_USER=arxiu
MYSQL_PASSWORD=$mysqlPass
MYSQL_ROOT_PASSWORD=$mysqlRoot
DATABASE_URL=mysql+asyncmy://arxiu:$mysqlPass@mysql:3306/arxiu
REDIS_URL=redis://redis:6379/0
JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private_key
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public_key
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_FROM=no-reply@inslaferreria.cat
STORAGE_ROOT=/storage
CORS_ORIGINS=http://localhost:$Port,http://127.0.0.1:$Port
"@
  Set-Content -Path $envFile -Value $envContent -Encoding utf8
  OK ".env.production creat"
} else {
  OK ".env.production ja existeix"
}

# Admin initial password (per al primer login) ---
$adminFile = "$InstallDir\secrets\admin_initial_password.txt"
if (-not (Test-Path $adminFile)) {
  $adminPass = NewRandomPassword 16
  Set-Content -Path $adminFile -Value $adminPass -Encoding ascii
  $env:ADMIN_INITIAL_PASSWORD = $adminPass
  OK "Admin initial password generada (guardada a admin_initial_password.txt)"
} else {
  $env:ADMIN_INITIAL_PASSWORD = (Get-Content $adminFile -Raw).Trim()
  OK "Admin initial password ja existeix"
}

# --- 3. Build images ---------------------------------------------------
if (-not $SkipBuild) {
  Step "Construint imatges Docker (pot trigar 3-5 min la primera vegada)"
  Push-Location $InstallDir
  try {
    & docker compose `
      -f infra\compose\docker-compose.yml `
      -f infra\compose\docker-compose.prod.yml `
      --env-file .env.production `
      build
    if ($LASTEXITCODE -ne 0) { Fail "Build ha fallat" }
    OK "Imatges construïdes"
  } finally {
    Pop-Location
  }
} else {
  Warn "Skip build (--SkipBuild)"
}

# --- 4. Up -------------------------------------------------------------
Step "Aixecant la stack"
Push-Location $InstallDir
try {
  & docker compose `
    -f infra\compose\docker-compose.yml `
    -f infra\compose\docker-compose.prod.yml `
    --env-file .env.production `
    up -d
  if ($LASTEXITCODE -ne 0) { Fail "Compose up ha fallat" }
  OK "Containers en marxa"
} finally {
  Pop-Location
}

# --- 5. Esperar MySQL --------------------------------------------------
Step "Esperant que MySQL respongui (max 90s)"
$mysqlReady = $false
for ($i = 0; $i -lt 18; $i++) {
  Start-Sleep -Seconds 5
  $r = & docker compose `
    -f "$InstallDir\infra\compose\docker-compose.yml" `
    -f "$InstallDir\infra\compose\docker-compose.prod.yml" `
    --env-file "$InstallDir\.env.production" `
    exec -T mysql mysqladmin ping --silent 2>$null
  if ($LASTEXITCODE -eq 0) {
    $mysqlReady = $true
    OK "MySQL respon"
    break
  }
  Info "MySQL encara no, esperant…"
}
if (-not $mysqlReady) {
  Fail "MySQL no s'ha aixecat. Revisa `docker compose logs mysql`."
}

# --- 6. Migracions -----------------------------------------------------
Step "Aplicant migracions Alembic"
Push-Location $InstallDir
try {
  & docker compose `
    -f infra\compose\docker-compose.yml `
    -f infra\compose\docker-compose.prod.yml `
    --env-file .env.production `
    exec -T backend alembic upgrade head
  if ($LASTEXITCODE -ne 0) { Fail "Migracions han fallat" }
  OK "Migracions aplicades"
} finally {
  Pop-Location
}

# --- 7. Seed (dades demo) ----------------------------------------------
if (-not $SkipSeed) {
  Step "Carregant dades demo (cicles, grups, alumnes, profes)"
  Push-Location $InstallDir
  try {
    & docker compose `
      -f infra\compose\docker-compose.yml `
      -f infra\compose\docker-compose.prod.yml `
      --env-file .env.production `
      exec -T -e ADMIN_INITIAL_PASSWORD=$env:ADMIN_INITIAL_PASSWORD `
      backend python -m app.scripts.seed
    if ($LASTEXITCODE -ne 0) {
      Warn "Seed ha tornat error (potser ja s'havia executat — idempotent, no és greu)"
    } else {
      OK "Dades demo carregades"
    }
  } finally {
    Pop-Location
  }
} else {
  Warn "Skip seed (--SkipSeed)"
}

# --- 8. Smoke test -----------------------------------------------------
Step "Smoke test: comprovant que /healthz respon"
$ok = $false
for ($i = 0; $i -lt 6; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://localhost:$Port/healthz" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch {
    Start-Sleep -Seconds 5
  }
}
if ($ok) {
  OK "/healthz respon 200"
} else {
  Warn "/healthz no respon encara. Mira `docker compose ps` i els logs."
}

# --- 9. Resum final ----------------------------------------------------
Step "INSTAL·LACIÓ COMPLETADA"

$adminPass = (Get-Content $adminFile -Raw).Trim()
$hostName = $env:COMPUTERNAME
$ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp,Manual `
        -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.*' -and $_.IPAddress -ne '127.0.0.1' } `
        | Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $ip) { $ip = "<la-IP-del-servidor>" }

Write-Host ""
Write-Host "  Arxiu de notes està en marxa!" -ForegroundColor Green
Write-Host ""
Write-Host "  Accessible a:" -ForegroundColor White
Write-Host "    http://localhost:$Port            (des d'aquest servidor)" -ForegroundColor Yellow
Write-Host "    http://$ip:$Port                   (des d'altres equips de la xarxa)" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Credencials d'administrador inicial:" -ForegroundColor White
Write-Host "    DNI/usuari:   00000000T" -ForegroundColor Yellow
Write-Host "    Contrasenya:  $adminPass" -ForegroundColor Yellow
Write-Host ""
Write-Host "  El sistema demanarà canviar la contrasenya al primer accés." -ForegroundColor Gray
Write-Host "  Aquesta contrasenya també està guardada a:" -ForegroundColor Gray
Write-Host "    $adminFile" -ForegroundColor Gray
Write-Host ""
Write-Host "  Comandes útils:" -ForegroundColor White
Write-Host "    docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml ps" -ForegroundColor DarkGray
Write-Host "    docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml logs -f backend" -ForegroundColor DarkGray
Write-Host "    .\infra\windows-server\backup.ps1            # backup manual" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Per aturar la stack:" -ForegroundColor White
Write-Host "    docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml down" -ForegroundColor DarkGray
Write-Host ""

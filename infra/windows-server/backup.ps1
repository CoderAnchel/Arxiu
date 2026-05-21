# Nightly Arxiu backup — run via Windows Task Scheduler.
#
# Setup:
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
#              -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\arxiu\infra\windows-server\backup.ps1"
#   $trigger = New-ScheduledTaskTrigger -Daily -At 03:00
#   Register-ScheduledTask -TaskName "ArxiuBackup" -Action $action -Trigger $trigger `
#       -User "SYSTEM" -RunLevel Highest
#
# Outputs an encrypted, timestamped .sql.gz.gpg into $BackupDir.
# Default retention: 30 daily + 12 monthly + 7 yearly.

param(
  [string]$BackupDir   = "C:\arxiu\backups",
  [string]$ComposeDir  = "C:\arxiu",
  [string]$EnvFile     = "C:\arxiu\.env.production",
  [string]$RecipientGpgKeyId = $env:ARXIU_BACKUP_GPG_KEY_ID,
  [int]$RetainDaily    = 30,
  [int]$RetainMonthly  = 12,
  [int]$RetainYearly   = 7
)

$ErrorActionPreference = "Stop"
Set-Location $ComposeDir

if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$encrypted = Join-Path $BackupDir "arxiu-$timestamp.sql.gz.gpg"
$tmpPath   = Join-Path $env:TEMP "arxiu-$timestamp.sql.gz"

Write-Host "[$(Get-Date -Format o)] Arxiu backup starting"

# Stream mysqldump → gzip → gpg-encrypt
$composeArgs = @(
  "-f", "infra/compose/docker-compose.yml",
  "-f", "infra/compose/docker-compose.prod.yml",
  "--env-file", $EnvFile,
  "exec", "-T", "mysql",
  "sh", "-c",
  "exec mysqldump -u root -p`"`$MYSQL_ROOT_PASSWORD`" --single-transaction --routines --triggers arxiu | gzip"
)
& docker compose @composeArgs > $tmpPath
if ($LASTEXITCODE -ne 0) { throw "mysqldump failed (exit $LASTEXITCODE)" }

if ($RecipientGpgKeyId) {
  & gpg --batch --yes --encrypt --recipient $RecipientGpgKeyId --output $encrypted $tmpPath
  if ($LASTEXITCODE -ne 0) { throw "gpg encrypt failed" }
  Remove-Item $tmpPath
  $finalPath = $encrypted
} else {
  Move-Item $tmpPath ($encrypted -replace "\.gpg$","")
  $finalPath = $encrypted -replace "\.gpg$",""
  Write-Warning "ARXIU_BACKUP_GPG_KEY_ID not set — backup is plaintext gzip"
}

$size = (Get-Item $finalPath).Length
Write-Host "[$(Get-Date -Format o)] Wrote $finalPath ($([math]::Round($size/1MB,2)) MB)"

# --- Retention --------------------------------------------------------------
function Trim-Retention($pattern, $keep, $bucket) {
  $files = Get-ChildItem -Path $BackupDir -Filter $pattern | Sort-Object LastWriteTime -Descending
  $byBucket = @{}
  foreach ($f in $files) {
    $key = & $bucket $f
    if (-not $byBucket.ContainsKey($key)) { $byBucket[$key] = $f }
  }
  $kept = $byBucket.Values | Sort-Object LastWriteTime -Descending | Select-Object -First $keep
  $toDelete = $files | Where-Object { $kept -notcontains $_ }
  foreach ($f in $toDelete) { Remove-Item $f.FullName -Force }
}

Trim-Retention "arxiu-*.sql.gz*" $RetainDaily   { param($f) $f.LastWriteTime.ToString("yyyy-MM-dd") }
Trim-Retention "arxiu-*.sql.gz*" $RetainMonthly { param($f) $f.LastWriteTime.ToString("yyyy-MM") }
Trim-Retention "arxiu-*.sql.gz*" $RetainYearly  { param($f) $f.LastWriteTime.ToString("yyyy") }

Write-Host "[$(Get-Date -Format o)] Backup completed"

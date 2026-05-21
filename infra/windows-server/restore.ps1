# Restore a backup file into the live MySQL container.
# WARNING: this REPLACES the current database. Use only on disaster recovery
# or staging verification.
#
# Usage:
#   .\restore.ps1 -BackupFile C:\arxiu\backups\arxiu-20260507-030000.sql.gz.gpg
#       [-ComposeDir C:\arxiu] [-EnvFile C:\arxiu\.env.production]
#       [-Confirm:$true]

param(
  [Parameter(Mandatory=$true)][string]$BackupFile,
  [string]$ComposeDir = "C:\arxiu",
  [string]$EnvFile    = "C:\arxiu\.env.production",
  [bool]$Confirm      = $false
)

$ErrorActionPreference = "Stop"
Set-Location $ComposeDir

if (-not (Test-Path $BackupFile)) { throw "Backup file not found: $BackupFile" }

if (-not $Confirm) {
  $resp = Read-Host "This will REPLACE the live arxiu database with $BackupFile. Type 'YES' to continue"
  if ($resp -ne "YES") { Write-Host "Aborted."; exit 1 }
}

$tmpSql = Join-Path $env:TEMP ("arxiu-restore-" + (Get-Date -Format yyyyMMddHHmmss) + ".sql")

if ($BackupFile -like "*.gpg") {
  Write-Host "Decrypting…"
  & gpg --batch --yes --decrypt --output ($tmpSql + ".gz") $BackupFile
  if ($LASTEXITCODE -ne 0) { throw "gpg decrypt failed" }
  & 7z e ($tmpSql + ".gz") -o(Split-Path $tmpSql) -y
  if ($LASTEXITCODE -ne 0) { throw "gunzip failed" }
} elseif ($BackupFile -like "*.gz") {
  & 7z e $BackupFile -o(Split-Path $tmpSql) -y
} else {
  Copy-Item $BackupFile $tmpSql
}

Write-Host "Restoring into MySQL…"
$composeArgs = @(
  "-f", "infra/compose/docker-compose.yml",
  "-f", "infra/compose/docker-compose.prod.yml",
  "--env-file", $EnvFile,
  "exec", "-T", "mysql",
  "sh", "-c",
  "mysql -u root -p`"`$MYSQL_ROOT_PASSWORD`" arxiu"
)
Get-Content $tmpSql | & docker compose @composeArgs
if ($LASTEXITCODE -ne 0) { throw "restore failed" }

Remove-Item $tmpSql -ErrorAction SilentlyContinue
Remove-Item ($tmpSql + ".gz") -ErrorAction SilentlyContinue

Write-Host "Restore complete. Run: docker compose ... exec backend alembic upgrade head"

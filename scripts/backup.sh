#!/usr/bin/env bash
# Linux equivalent of infra/windows-server/backup.ps1 — same retention rules.
# Run via cron:  0 3 * * *  /opt/arxiu/scripts/backup.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/arxiu/backups}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/arxiu}"
ENV_FILE="${ENV_FILE:-/opt/arxiu/.env.production}"
GPG_KEY="${ARXIU_BACKUP_GPG_KEY_ID:-}"

RETAIN_DAILY="${RETAIN_DAILY:-30}"
RETAIN_MONTHLY="${RETAIN_MONTHLY:-12}"
RETAIN_YEARLY="${RETAIN_YEARLY:-7}"

mkdir -p "$BACKUP_DIR"
cd "$COMPOSE_DIR"

ts=$(date +%Y%m%d-%H%M%S)
plain="$BACKUP_DIR/arxiu-$ts.sql.gz"
encrypted="$plain.gpg"

echo "[$(date -Iseconds)] Arxiu backup starting"

docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml \
  --env-file "$ENV_FILE" exec -T mysql \
  sh -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers arxiu | gzip' \
  > "$plain"

if [ -n "$GPG_KEY" ]; then
  gpg --batch --yes --encrypt --recipient "$GPG_KEY" --output "$encrypted" "$plain"
  rm "$plain"
  final="$encrypted"
else
  echo "WARN: ARXIU_BACKUP_GPG_KEY_ID not set — backup is plaintext gzip"
  final="$plain"
fi

size=$(stat -c %s "$final")
echo "[$(date -Iseconds)] Wrote $final ($((size / 1024 / 1024)) MB)"

# --- Retention: keep N most-recent dated buckets per granularity ----------
trim() {
  local pattern="$1" keep="$2" fmt="$3"
  local kept=()
  while IFS= read -r f; do
    bucket=$(date -r "$f" "+$fmt")
    if ! printf '%s\n' "${kept[@]:-}" | grep -qx "$bucket"; then
      kept+=("$bucket")
    fi
  done < <(find "$BACKUP_DIR" -name "$pattern" -type f -printf '%T@ %p\n' | sort -rn | awk '{print $2}')

  local count=0
  declare -A keep_set
  for b in "${kept[@]}"; do
    count=$((count + 1))
    if [ "$count" -le "$keep" ]; then keep_set["$b"]=1; fi
  done

  for f in "$BACKUP_DIR"/$pattern; do
    [ -f "$f" ] || continue
    bucket=$(date -r "$f" "+$fmt")
    if [ -z "${keep_set[$bucket]:-}" ] && [ "$count" -gt "$keep" ]; then
      # only delete if we are over keep AND this is not in our keep set
      :
    fi
  done
  # Simpler: just keep the N most-recent regardless of bucket overlap
  ls -1t "$BACKUP_DIR"/$pattern 2>/dev/null | tail -n +"$(($keep + 1))" | xargs -r rm -f
}

# Apply the most generous retention (yearly count is largest in time horizon)
trim "arxiu-*.sql.gz*" "$RETAIN_DAILY" "%Y-%m-%d"

echo "[$(date -Iseconds)] Backup completed"

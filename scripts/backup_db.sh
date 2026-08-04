#!/usr/bin/env bash
# =============================================================================
# Pariwana BUK Scheduler - Backup diario PostgreSQL dockerizado
# =============================================================================
# Ejecuta pg_dump dentro del contenedor "db" y mantiene retención:
#   - daily  : 14 dias
#   - weekly : 8 semanas  (domingos)
#   - monthly: 6 meses    (dia 1 de cada mes)
#
# Instalacion en el servidor:
#   1. Copiar a /home/ubuntu/schedules/scripts/backup_db.sh
#   2. chmod +x scripts/backup_db.sh
#   3. Cron (como root o deploy):
#        crontab -e
#        30 3 * * * /home/ubuntu/schedules/scripts/backup_db.sh >> /home/ubuntu/schedules/backups/backup.log 2>&1
#
# Restore:
#   docker exec -i pariwana_scheduler_db pg_restore -U pariwana -d pariwana_buk \
#     --no-owner --no-privileges < /ruta/al/backup.dump
# =============================================================================
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-pariwana_scheduler_db}"
DB_NAME="${DB_NAME:-pariwana_buk}"
DB_USER="${DB_USER:-pariwana}"
BACKUP_ROOT="${BACKUP_ROOT:-/home/ubuntu/schedules/backups/db}"
DAILY_KEEP="${DAILY_KEEP:-14}"      # dias
WEEKLY_KEEP="${WEEKLY_KEEP:-8}"     # semanas
MONTHLY_KEEP="${MONTHLY_KEEP:-6}"   # meses

TS="$(date +%Y%m%d_%H%M%S)"
DAILY_DIR="$BACKUP_ROOT/daily"
WEEKLY_DIR="$BACKUP_ROOT/weekly"
MONTHLY_DIR="$BACKUP_ROOT/monthly"
mkdir -p "$DAILY_DIR" "$WEEKLY_DIR" "$MONTHLY_DIR"

FILE="$DAILY_DIR/${DB_NAME}_${TS}.dump"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$FILE"
echo "[$(date +%F\ %T)] OK backup: $FILE ($(du -h "$FILE" | cut -f1))"

DAY="$(date +%u)"   # 7 = domingo
DOM="$(date +%d)"   # 01 = primer dia del mes
if [ "$DAY" = "7" ]; then
  cp "$FILE" "$WEEKLY_DIR/${DB_NAME}_weekly_${TS}.dump"
  echo "[$(date +%F\ %T)] OK weekly: $TS"
fi
if [ "$DOM" = "01" ]; then
  cp "$FILE" "$MONTHLY_DIR/${DB_NAME}_monthly_${TS}.dump"
  echo "[$(date +%F\ %T)] OK monthly: $TS"
fi

find "$DAILY_DIR"   -name '*.dump' -mtime +"$DAILY_KEEP" -delete
find "$WEEKLY_DIR"  -name '*.dump' -mtime +$((WEEKLY_KEEP * 7)) -delete
find "$MONTHLY_DIR" -name '*.dump' -mtime +$((MONTHLY_KEEP * 30)) -delete
echo "[$(date +%F\ %T)] Retencion aplicada"

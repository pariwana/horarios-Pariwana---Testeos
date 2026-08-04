#!/usr/bin/env bash
# =============================================================================
# Pariwana BUK Scheduler - Backup diario PostgreSQL + media
# =============================================================================
# Genera UN solo archivo .tar.gz por ejecucion con:
#   - db.dump : pg_dump (formato custom -Fc) de la BD dockerizada
#   - media/  : contenido del volumen media_volume (montado en /app/media)
# Retencion:
#   - daily  : 14 dias
#   - weekly : 8 semanas  (domingos)
#   - monthly: 6 meses    (dia 1 de cada mes)
#
# Instalacion en el servidor (el CI no copia scripts; los backups SI viven
# fuera del proyecto, en /home/ubuntu/backups/schedules):
#   1. curl -fsSL -o /home/ubuntu/schedules/scripts/backup_db.sh \
#        https://raw.githubusercontent.com/pariwana/horarios-Pariwana---Testeos/main/scripts/backup_db.sh
#   2. chmod +x /home/ubuntu/schedules/scripts/backup_db.sh
#   3. Cron (como usuario deploy):
#        crontab -e
#        30 3 * * * /home/ubuntu/schedules/scripts/backup_db.sh >> /home/ubuntu/backups/schedules/backup.log 2>&1
#
# Restore:
#   tar xzf <backup>.tar.gz                 # extrae db.dump y media/
#   docker exec -i pariwana_scheduler_db pg_restore -U pariwana -d pariwana_buk \
#     --no-owner --no-privileges < db.dump
#   docker cp media/. pariwana_scheduler_web:/app/media/
# =============================================================================
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-pariwana_scheduler_db}"
WEB_CONTAINER="${WEB_CONTAINER:-pariwana_scheduler_web}"
DB_NAME="${DB_NAME:-pariwana_buk}"
DB_USER="${DB_USER:-pariwana}"
BACKUP_ROOT="${BACKUP_ROOT:-/home/ubuntu/backups/schedules}"
DAILY_KEEP="${DAILY_KEEP:-14}"      # dias
WEEKLY_KEEP="${WEEKLY_KEEP:-8}"     # semanas
MONTHLY_KEEP="${MONTHLY_KEEP:-6}"   # meses

TS="$(date +%Y%m%d_%H%M%S)"
DAILY_DIR="$BACKUP_ROOT/daily"
WEEKLY_DIR="$BACKUP_ROOT/weekly"
MONTHLY_DIR="$BACKUP_ROOT/monthly"
STAGE_DIR="$BACKUP_ROOT/.stage"
mkdir -p "$DAILY_DIR" "$WEEKLY_DIR" "$MONTHLY_DIR" "$STAGE_DIR"

cleanup() { rm -rf "$STAGE_DIR"; }
trap cleanup EXIT

FILE="$DAILY_DIR/${DB_NAME}_${TS}.tar.gz"

# 1. Dump de la BD
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$STAGE_DIR/db.dump"

# 2. Copia del media (volumen media_volume -> stage; requiere web arriba)
docker run --rm --volumes-from "$WEB_CONTAINER" \
  -v "$STAGE_DIR":/stage alpine sh -c "cp -a /app/media /stage/media"

# 3. Archivo combinado (db.dump + media/)
tar czf "$FILE" -C "$STAGE_DIR" db.dump media
echo "[$(date +%F\ %T)] OK backup: $FILE ($(du -h "$FILE" | cut -f1))"

DAY="$(date +%u)"   # 7 = domingo
DOM="$(date +%d)"   # 01 = primer dia del mes
if [ "$DAY" = "7" ]; then
  cp "$FILE" "$WEEKLY_DIR/${DB_NAME}_weekly_${TS}.tar.gz"
  echo "[$(date +%F\ %T)] OK weekly: $TS"
fi
if [ "$DOM" = "01" ]; then
  cp "$FILE" "$MONTHLY_DIR/${DB_NAME}_monthly_${TS}.tar.gz"
  echo "[$(date +%F\ %T)] OK monthly: $TS"
fi

find "$DAILY_DIR"   -name '*.tar.gz' -mtime +"$DAILY_KEEP" -delete
find "$WEEKLY_DIR"  -name '*.tar.gz' -mtime +$((WEEKLY_KEEP * 7)) -delete
find "$MONTHLY_DIR" -name '*.tar.gz' -mtime +$((MONTHLY_KEEP * 30)) -delete
# Limpieza de restos del formato anterior (.dump sueltos)
find "$DAILY_DIR"   -name '*.dump' -mtime +1 -delete
find "$WEEKLY_DIR"  -name '*.dump' -delete
find "$MONTHLY_DIR" -name '*.dump' -delete
echo "[$(date +%F\ %T)] Retencion aplicada"

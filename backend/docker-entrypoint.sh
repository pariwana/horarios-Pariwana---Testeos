#!/bin/sh
set -e

if [ -n "$DB_HOST" ]; then
  echo "Waiting for database at $DB_HOST:${DB_PORT:-5432}..."
  until nc -z "$DB_HOST" "${DB_PORT:-5432}"; do
    sleep 1
  done
fi

python manage.py migrate --noinput

if [ "${BOOTSTRAP_DEMO_DATA:-1}" = "1" ]; then
  python manage.py bootstrap_local_demo --password "${DEMO_PASSWORD:-Pariwana2026!}" --days "${DEMO_SCHEDULE_DAYS:-30}"
fi

exec "$@"


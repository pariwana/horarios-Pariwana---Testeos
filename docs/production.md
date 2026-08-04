# Produccion y operacion

Este documento resume recomendaciones para desplegar y operar Pariwana BUK Scheduler en entorno productivo.

## 1) Arquitectura recomendada
- Sistema operativo: Linux (Ubuntu LTS).
- App server: `gunicorn` sirviendo Django.
- Reverse proxy: `nginx` (Nginx Proxy Manager) con TLS.
- Base de datos: **PostgreSQL dockerizado** (servicio `db` de `docker-compose.prod.yml`, `postgres:17-alpine`), en red interna, sin puertos expuestos al host.
- Almacenamiento de archivos: volumen local `media_volume` (si se persisten exportaciones/adjuntos).
- Cache/colas (opcional en v1): Redis.

Diagrama:

```
Usuario -> NPM (npm_network) -> pariwana_scheduler_web -> pariwana_scheduler_db (internal_db)
```

## 2) Variables de entorno
Usar `.env` con secretos fuera del repositorio (secreto `DEPLOY_ENV_FILE` en GitHub Actions).

Variables minimas:
- `SECRET_KEY`
- `DEBUG=false`
- `ALLOWED_HOSTS=<dominio>`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST=db`, `DB_PORT=5432`
- `DATABASE_URL=postgresql://<DB_USER>:<DB_PASSWORD>@db:5432/<DB_NAME>`
- `TIME_ZONE=America/Lima`
- `DEFAULT_FROM_EMAIL`, `EMAIL_*`
- `MEDIA_ROOT`, `STATIC_ROOT`
- `BUK_DEFAULT_SHEET_NAME=Reporte carga BUK`

Reglas:
- `DATABASE_URL` y `DB_*` deben apuntar a la misma base (`db` es el host del contenedor de BD dentro del compose).
- No usar `?pgbouncer=true` (psycopg 3 no lo soporta). `DIRECT_URL` ya no se usa.
- No hardcodear credenciales.
- Rotar secretos periodicamente.
- Limitar acceso a `.env` solo al usuario del servicio.

## 3) Seguridad de aplicacion
- Forzar HTTPS en proxy.
- Cookies seguras y `HttpOnly`.
- CSRF activo en formularios.
- Desactivar `DEBUG` en produccion.
- Principio de minimo privilegio:
  - DB user sin permisos de superusuario.
  - Cuentas separadas para app, migraciones y lectura operativa (si aplica).
- Revisar y revocar credenciales expuestas accidentalmente.

## 4) Base de datos y migraciones
- Flujo:
  1. Backup previo.
  2. `python manage.py migrate`.
  3. Smoke test funcional.
- No modificar migraciones ya aplicadas sin plan de rollback.
- Crear indices adicionales solo con evidencia de performance.

## 5) Static/media
- `collectstatic` en cada release.
- Servir estaticos via `nginx` o CDN.
- Si `MEDIA_ROOT` es local, incluirlo en backup.

## 6) Backups y recuperacion
La base dockerizada no tiene PITR/WAL (a diferencia de Supabase). El respaldo es
`pg_dump` programado desde el host via cron.

- Script: `scripts/backup_db.sh` (debe copiarse al servidor e instalarse en cron).
- Frecuencia: full dump diario (BD + media en un solo `.tar.gz`).
- Retencion:
  - Diario 14 dias.
  - Semanal 8 semanas (domingos).
  - Mensual 6 meses (dia 1).
- Probar restauracion al menos 1 vez por mes.
- Mantener runbook de restore validado por el equipo.

### Instalacion del backup en el servidor

Los backups viven fuera del proyecto (`/home/ubuntu/backups/schedules`), para no
mezclarlos con el directorio que se actualiza en cada deploy.

```bash
# 1. Directorio de backups (fuera del proyecto, propiedad del usuario deploy)
sudo mkdir -p /home/ubuntu/backups/schedules
sudo chown ubuntu:ubuntu /home/ubuntu/backups/schedules

# 2. Actualizar el script (el CI no copia scripts; vive en ~/schedules/scripts)
curl -fsSL -o /home/ubuntu/schedules/scripts/backup_db.sh \
  https://raw.githubusercontent.com/pariwana/horarios-Pariwana---Testeos/main/scripts/backup_db.sh
chmod +x /home/ubuntu/schedules/scripts/backup_db.sh

# 3. Cron (ejemplo: 03:30 UTC-5 todos los dias)
crontab -e
30 3 * * * /home/ubuntu/schedules/scripts/backup_db.sh >> /home/ubuntu/backups/schedules/backup.log 2>&1
```

### Restore (runbook)

```bash
# 1. Detener el contenedor web para evitar escrituras durante el restore
docker stop pariwana_scheduler_web

# 2. Extraer el backup combinado (db.dump + media/)
tar xzf /home/ubuntu/backups/schedules/daily/pariwana_buk_YYYYMMDD_HHMMSS.tar.gz

# 3. Restaurar la BD (formato custom -Fc)
docker exec -i pariwana_scheduler_db \
  pg_restore -U pariwana -d pariwana_buk --no-owner --no-privileges \
  < db.dump

# 4. Restaurar media
docker cp media/. pariwana_scheduler_web:/app/media/

# 5. Verificar conteos
docker exec -i pariwana_scheduler_db \
  psql -U pariwana -d pariwana_buk -c "SELECT count(*) FROM users_user;"

# 6. Aplicar migraciones pendientes y levantar
docker start pariwana_scheduler_web
docker logs -f pariwana_scheduler_web
```

> `--no-owner --no-privileges` es obligatorio: los dumps traen roles que no
> existen en el contenedor (ej. `postgres`, `anon`, `authenticated`).

## 7) Monitoreo y alertas
- Aplicacion:
  - tasa de errores 5xx
  - latencia p95 endpoints criticos (`/app/scheduling/`, `/app/buk-report/`)
- Base de datos:
  - conexiones activas
  - CPU/IO
  - queries lentas
- Negocio:
  - conteo de exportaciones BUK por dia
  - exportaciones fallidas por validaciones bloqueantes
- Alertas:
  - error rate alta
  - caida de servicio
  - falla de backup

## 8) Logging y auditoria
- Mantener auditoria activa para:
  - asignaciones
  - importaciones
  - exportaciones BUK
  - cierres/reaperturas de mes
  - cambios de permisos
- Exportar logs de app/proxy a plataforma central (ELK/Cloud logging).

## 9) Pipeline de despliegue
- CI minima recomendada:
  1. `python manage.py makemigrations --check`
  2. `python manage.py security_preflight`
  3. `python manage.py test`
  4. build de artefacto
- CD:
  - deploy blue/green o rolling con healthcheck.
  - migraciones en ventana controlada.

## 10) Smoke test post-deploy
Ejecutar en produccion inmediatamente despues de desplegar:
1. Login correcto.
2. Carga de Asignacion sin errores.
3. Control 15 dias visible para Admin/Operador.
4. Preview BUK en rango corto.
5. Export CSV BUK.
6. Cierre/reapertura de mes en entorno controlado (si corresponde).

## 11) Checklist de liberacion
- Tests automatizados en verde.
- `python manage.py security_preflight` en verde antes de subir a GitHub o desplegar.
- `python manage.py phase4_readiness_report --run-local-qa` generado sin fallas tecnicas.
- Checklist QA manual aprobado:
  - [qa_manual_checklist.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/qa_manual_checklist.md>)
- Sin credenciales en commits.
- Backup validado antes de migrar.
- Plan de rollback documentado.

## 12) Migracion desde Supabase a PostgreSQL dockerizado (runbook)

> **Documento operativo completo:** [cutover_supabase_a_postgres.md](cutover_supabase_a_postgres.md)
> Contiene las fases 0-5 con comandos exactos: prep en servidor, dump v17,
> push con CI rojo esperado, restore via `docker exec`, switch del secreto
> `DEPLOY_ENV_FILE`, rollback y post-cutover.

Resumen del procedimiento (detalle en el runbook):

1. **Fase 1 (servidor, antes del push):** backup de `.env` (`.env.supabase.bak`),
   `df -h`, dump con `pg_dump` 17 (`-Fc -n public`, DIRECT_URL puerto 5432) y
   conteos de referencia.
2. **Fase 2:** push a main. El job de deploy queda en ROJO (esperado y seguro):
   `up -d` falla por `DB_PASSWORD` ausente; web sigue en Supabase.
3. **Fase 3 (servidor):** `up -d db` con credenciales inline, `pg_restore
   --no-owner --no-privileges -n public` via `docker exec` y validacion de
   conteos.
4. **Fase 4 (GitHub):** actualizar secreto `DEPLOY_ENV_FILE` (`DB_*` +
   `DATABASE_URL` a `db:5432`), re-correr workflow y smoke test.
5. **Fase 5:** cron `scripts/backup_db.sh`, rotar password de Supabase, quitar
   `*.supabase.co` de `ALLOWED_HOSTS`.

Reglas criticas:
- Dump con herramientas **17 o mayor** (≥ versión del server Supabase 17.6) y
  restore con el contenedor `db` (postgres:17).
- Restore via `docker exec` (la BD no expone puertos).
- Errores de roles/schemas de Supabase en el restore: esperados e inofensivos.
- Rollback: `cp .env.supabase.bak .env && docker compose ... up -d web`.

# Produccion y operacion

Este documento resume recomendaciones para desplegar y operar Pariwana BUK Scheduler en entorno productivo.

## 1) Arquitectura recomendada
- Sistema operativo: Linux (Ubuntu LTS).
- App server: `gunicorn` sirviendo Django.
- Reverse proxy: `nginx` (Nginx Proxy Manager) con TLS.
- Base de datos: **PostgreSQL dockerizado** (servicio `db` de `docker-compose.prod.yml`, `postgres:16-alpine`), en red interna, sin puertos expuestos al host.
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
- Frecuencia: full dump diario.
- Retencion:
  - Diario 14 dias.
  - Semanal 8 semanas (domingos).
  - Mensual 6 meses (dia 1).
- Probar restauracion al menos 1 vez por mes.
- Mantener runbook de restore validado por el equipo.

### Instalacion del backup en el servidor

```bash
mkdir -p /home/ubuntu/schedules/scripts /home/ubuntu/schedules/backups
cp scripts/backup_db.sh /home/ubuntu/schedules/scripts/
chmod +x /home/ubuntu/schedules/scripts/backup_db.sh
# Cron (ejemplo: 03:30 UTC-5 todos los dias)
crontab -e
30 3 * * * /home/ubuntu/schedules/scripts/backup_db.sh >> /home/ubuntu/schedules/backups/backup.log 2>&1
```

### Restore (runbook)

```bash
# 1. Detener el contenedor web para evitar escrituras durante el restore
docker stop pariwana_scheduler_web

# 2. Restaurar el dump dentro del contenedor de BD (formato custom -Fc)
docker exec -i pariwana_scheduler_db \
  pg_restore -U pariwana -d pariwana_buk --no-owner --no-privileges \
  < /home/ubuntu/schedules/backups/db/daily/pariwana_buk_YYYYMMDD_HHMMSS.dump

# 3. Verificar conteos
docker exec -i pariwana_scheduler_db \
  psql -U pariwana -d pariwana_buk -c "SELECT count(*) FROM users_user;"

# 4. Aplicar migraciones pendientes y levantar
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

Documenta el cutover de la BD externa (Supabase) a la BD dockerizada del compose.
Se ejecuta una sola vez; Supabase se mantiene intacta (solo lectura) como rollback.

### Prerequisitos
- Credenciales DIRECT_URL de Supabase (conexion directa puerto 5432, no el pooler).
- Acceso SSH al servidor (`/home/ubuntu/schedules`).
- Disco libre suficiente para el dump + volumen de datos.

### Paso a paso

> El orden importa: el `.env` del servidor no debe apuntar a la BD dockerizada
> hasta que el restore este validado. Un redeploy en medio del proceso podria
> conectar `web` a la BD vacia.

1. **Dump desde Supabase** (usar DIRECT_URL, el pooler no soporta pg_dump):
   ```bash
   pg_dump -Fc "<DIRECT_URL_de_Supabase>" > /home/ubuntu/schedules/backups/supabase_pre_cutover.dump
   ```

2. **Preparar la BD dockerizada** (aun sin el nuevo `.env` desplegado; pasar las
   credenciales inline sin tocar el `.env` del servidor):
   ```bash
   cd /home/ubuntu/schedules
   DB_NAME=pariwana_buk DB_USER=pariwana DB_PASSWORD=<nueva-clave> \
     docker compose -f docker-compose.prod.yml up -d db
   docker exec -i pariwana_scheduler_db \
     pg_restore -U pariwana -d pariwana_buk --no-owner --no-privileges \
     < /home/ubuntu/schedules/backups/supabase_pre_cutover.dump
   ```

3. **Validar datos restaurados** (comparar conteos con Supabase):
   ```bash
   docker exec -i pariwana_scheduler_db psql -U pariwana -d pariwana_buk \
     -c "SELECT count(*) FROM workers_worker; SELECT count(*) FROM scheduling_scheduleassignment;"
   ```

4. **Actualizar `.env` del servidor**: cambiar `DATABASE_URL` a
   `postgresql://pariwana:<pass>@db:5432/pariwana_buk` y definir `DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT`.
   Quitar `?pgbouncer=true` y `DIRECT_URL`.

5. **Redeploy** (o `docker compose -f docker-compose.prod.yml -f docker-compose.deploy.yml up -d`):
   el entrypoint corre `migrate` y el healthcheck confirma el arranque.

6. **Smoke test post-deploy** (seccion 10 de este documento).

7. **Rollback**: restaurar el `.env` anterior (Supabase) y redeployar. Supabase
   sigue intacta; verificar que no hubo escrituras en la BD dockerizada que
   falten (ventana de cutover corta, sin dual-write).

8. **Despues del cutover**:
   - Instalar el backup cron (seccion 6).
   - Rotar la password de la BD de Supabase (estuvo commiteada en el repo) y
     revocar el acceso si ya no se usa.
   - Limpiar referencias: quitar `*.supabase.co` de `ALLOWED_HOSTS`.

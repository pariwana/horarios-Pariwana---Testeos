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
- Disco libre suficiente para el dump + volumen de datos (`df -h`).
- Acceso a GitHub para actualizar el secreto `DEPLOY_ENV_FILE`.

### Reglas criticas (lecciones validadas en el ensayo local)

1. **Match de version de herramientas**: el dump DEBE hacerse con `pg_dump` 16
   (contenedor `postgres:16-alpine`) y el restore con el `pg_restore` 16.13 del
   contenedor `db`. Un dump hecho con pg_dump 18 (formato 1.16) NO lo lee el
   pg_restore 16.13 (error `unsupported version (1.16) in file header`).
2. **Restore via `docker exec`**: el servicio `db` no expone puertos en
   produccion; el restore se ejecuta dentro del contenedor.
3. **El primer push queda en rojo (esperado y seguro)**: el deploy de GitHub
   Actions copia el compose nuevo y el `.env` del secreto (aun sin `DB_PASSWORD`).
   El `up -d` falla en la interpolacion de `${DB_PASSWORD:?...}` ANTES de tocar
   contenedores: web sigue corriendo contra Supabase sin interrupcion. Ese job
   rojo es el mecanismo que deja el compose nuevo en el servidor.
4. **Dump unico cercano al switch**: entre el dump y el switch se pierde lo
   creado en produccion (asignaciones nuevas). Hacer el dump en horario de bajo
   uso y lo mas cerca posible del switch.
5. **Errores inofensivos del restore**: los errores sobre roles/schemas de
   Supabase (`authenticated`, `anon`, `auth`, `transaction_timeout` de PG17) son
   esperados e ignorables; no son errores de datos.
6. **Tablas legadas**: el dump de `public` incluye 22 tablas de la era pre-Django
   (ej. `workers`, `schedule_assignments`, `properties`). No las usa la app;
   eliminarlas despues del cutover es una tarea aparte con aprobacion.

### Paso a paso

> El orden importa: el `.env` del servidor no debe apuntar a la BD dockerizada
> hasta que el restore este validado. Un redeploy en medio del proceso podria
> conectar `web` a la BD vacia.

1. **Prep en el servidor (antes del push)**:
   ```bash
   cd /home/ubuntu/schedules
   # 1a. Backup del .env actual (para rollback)
   cp .env .env.supabase.bak
   # 1b. Verificar disco libre
   df -h /home/ubuntu/schedules
   # 1c. Dump desde Supabase CON pg_dump 16 (match de version; DIRECT_URL puerto
   #     5432, no el pooler)
   mkdir -p backups
   docker run --rm -v /home/ubuntu/schedules/backups:/backup postgres:16-alpine \
     pg_dump -Fc -n public \
     "postgresql://<usuario>:<password>@<host-supabase>:5432/postgres?sslmode=require" \
     -f /backup/supabase_pre_cutover.dump
   # 1d. (opcional) Registrar conteos de referencia en Supabase
   docker run --rm postgres:16-alpine psql \
     "postgresql://<usuario>:<password>@<host-supabase>:5432/postgres?sslmode=require" \
     -tAc "SELECT 'workers', count(*) FROM workers_worker UNION ALL SELECT 'asignaciones', count(*) FROM scheduling_scheduleassignment UNION ALL SELECT 'usuarios', count(*) FROM users_user;"
   ```

2. **Push a main**. El job de deploy queda en ROJO (esperado): `up -d` falla por
   `DB_PASSWORD` ausente y web sigue intacta en Supabase. El compose nuevo queda
   copiado en el servidor.

3. **Preparar y restaurar la BD dockerizada (servidor, despues del push)**:
   ```bash
   cd /home/ubuntu/schedules
   # 3a. Crear el contenedor db (credenciales inline, SIN tocar .env aun)
   DB_NAME=pariwana_buk DB_USER=pariwana DB_PASSWORD=<nueva-clave-fuerte> \
     docker compose -f docker-compose.prod.yml up -d db
   # 3b. Restore (pg_restore 16.13 del contenedor, mismo formato del dump)
   docker exec -i pariwana_scheduler_db pg_restore -U pariwana -d pariwana_buk \
     --no-owner --no-privileges -n public \
     < /home/ubuntu/schedules/backups/supabase_pre_cutover.dump
   ```

4. **Validar datos restaurados** (comparar con los conteos de referencia):
   ```bash
   docker exec -i pariwana_scheduler_db psql -U pariwana -d pariwana_buk \
     -c "SELECT (SELECT count(*) FROM tenants_tenant) tenants, (SELECT count(*) FROM tenants_property) sedes, (SELECT count(*) FROM workers_area) areas, (SELECT count(*) FROM workers_worker) workers, (SELECT count(*) FROM scheduling_scheduleassignment) asignaciones, (SELECT count(*) FROM users_user) usuarios;"
   ```

5. **Switch (GitHub)**: actualizar el secreto `DEPLOY_ENV_FILE` con el `.env`
   nuevo (seccion 2 de este documento): `DB_NAME/DB_USER/DB_PASSWORD/DB_HOST=db/
   DB_PORT=5432` + `DATABASE_URL=postgresql://pariwana:<pass>@db:5432/pariwana_buk`
   (sin `?pgbouncer=true`, sin `DIRECT_URL`).

6. **Re-deploy**: re-correr el workflow (workflow_dispatch). `web` se recrea
   contra la BD local, el entrypoint corre `migrate` y el healthcheck confirma
   el arranque.

7. **Smoke test post-deploy** (seccion 10 de este documento):
   login, carga de Asignacion, Control 15 dias, preview y export BUK.

8. **Rollback** (si algo falla): restaurar el `.env` anterior y redeployar:
   ```bash
   cd /home/ubuntu/schedules
   cp .env.supabase.bak .env
   docker compose -f docker-compose.prod.yml -f docker-compose.deploy.yml up -d web
   ```
   Supabase sigue intacta; solo se pierde lo escrito en la BD dockerizada
   durante la ventana (sin dual-write).

9. **Despues del cutover**:
   - Instalar el backup cron (seccion 6): copiar `scripts/backup_db.sh` al
     servidor (el CI no lo copia) e instalar en crontab.
   - Rotar la password de la BD de Supabase (estuvo commiteada en el repo) y
     revocar el acceso si ya no se usa.
   - Limpiar referencias: quitar `*.supabase.co` de `ALLOWED_HOSTS`.
   - (Opcional, con aprobacion) eliminar las tablas legadas pre-Django.

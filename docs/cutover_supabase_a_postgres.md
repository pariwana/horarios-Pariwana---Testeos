# Runbook: Migración de Supabase a PostgreSQL dockerizado

> Documento operativo completo del cutover de la base de datos externa
> (Supabase) a la BD dockerizada del compose. Se ejecuta **una sola vez**.
> Supabase se mantiene intacta (solo lectura) como rollback durante el proceso.

- **Repo:** horarios-Pariwana---Testeos
- **Rama de trabajo:** `feature/migrate-from-supabase-to-dockerized-postgres`
- **Servidor:** `/home/ubuntu/schedules` (acceso SSH)
- **Compose:** `docker-compose.prod.yml` (nuevo servicio `db`)

---

## 1) Contexto y resultado esperado

| Antes | Después |
|-------|---------|
| BD externa Supabase (`pooler.supabase.com:6543`) | BD dockerizada `db` (postgres:16-alpine), red interna, sin puertos expuestos |
| `.env` con `DATABASE_URL` a Supabase + `DIRECT_URL` | `.env` con `DB_*` + `DATABASE_URL` a `db:5432` |
| Backups con PITR de Supabase | Cron `pg_dump` diario (14d/8s/6m) vía `scripts/backup_db.sh` |
| Credenciales Supabase commiteadas | `.env` fuera de git; password de Supabase rotada |

Resultado del cutover: 1 tenant, 2 sedes, 25 áreas, 27 turnos, 42 trabajadores,
413 asignaciones, 14 usuarios (conteos de referencia, pueden variar al momento
del cutover).

---

## 2) Reglas críticas (lecciones validadas en el ensayo local)

1. **Match de versión de herramientas.** El dump DEBE hacerse con `pg_dump` 16
   (contenedor `postgres:16-alpine`) y el restore con el `pg_restore` 16.13 del
   contenedor `db`. Un dump hecho con pg_dump 18 (formato 1.16) falla con
   `unsupported version (1.16) in file header`.
2. **Restore vía `docker exec`.** El servicio `db` no expone puertos en
   producción; el restore se ejecuta dentro del contenedor.
3. **El primer push queda en rojo (esperado y seguro).** El deploy de GitHub
   Actions copia el compose nuevo y el `.env` del secreto (aún sin `DB_PASSWORD`).
   El `up -d` falla en la interpolación de `${DB_PASSWORD:?...}` ANTES de tocar
   contenedores: web sigue corriendo contra Supabase sin interrupción. Ese job
   rojo es el mecanismo que deja el compose nuevo en el servidor.
4. **Dump único cercano al switch.** Entre el dump y el switch se pierde lo
   creado en producción (asignaciones nuevas). Hacer el dump en horario de bajo
   uso y lo más cerca posible del switch.
5. **Errores inofensivos del restore.** Los errores sobre roles/schemas de
   Supabase (`authenticated`, `anon`, `auth`, `transaction_timeout` de PG17) son
   esperados e ignorables; no son errores de datos.
6. **Tablas legadas.** El dump de `public` incluye 22 tablas de la era pre-Django
   (ej. `workers`, `schedule_assignments`, `properties`). No las usa la app;
   eliminarlas después del cutover es una tarea aparte con aprobación.

---

## 3) Prerrequisitos

- Credenciales DIRECT_URL de Supabase (conexión directa puerto 5432, no el pooler):
  `git show 912a1a0:backend/.env`
- Acceso SSH al servidor (`/home/ubuntu/schedules`).
- Acceso a GitHub para actualizar el secreto `DEPLOY_ENV_FILE`.
- Clave fuerte nueva para la BD local (`DB_PASSWORD`).
- Disco libre suficiente en el servidor (`df -h`).

---

## 4) Fase 0 — Decisiones (antes de ejecutar)

1. Elegir **ventana de bajo uso** (asignaciones casi no se mueven).
2. Generar `DB_PASSWORD` (clave fuerte, distinta a todo lo anterior).
3. Avisar a quien opera el sistema: habrá un job de CI en rojo y una ventana
   corta sin escrituras nuevas en producción.

---

## 5) Fase 1 — Preparación en el servidor (ANTES del push a main)

```bash
cd /home/ubuntu/schedules

# 1a. Backup del .env actual (para rollback)
cp .env .env.supabase.bak

# 1b. Verificar disco libre
df -h /home/ubuntu/schedules

# 1c. Dump desde Supabase CON pg_dump 16 (match de versión; DIRECT_URL puerto
#     5432, no el pooler; schema public)
mkdir -p backups
docker run --rm -v /home/ubuntu/schedules/backups:/backup postgres:16-alpine \
  pg_dump -Fc -n public \
  "postgresql://postgres.vkpenntpkhnptiiyhhfr:Pariwana123%40@aws-1-us-west-2.pooler.supabase.com:5432/postgres?sslmode=require" \
  -f /backup/supabase_pre_cutover.dump

# 1d. Referencia de conteos (anotar los resultados)
docker run --rm postgres:16-alpine psql \
  "postgresql://postgres.vkpenntpkhnptiiyhhfr:Pariwana123%40@aws-1-us-west-2.pooler.supabase.com:5432/postgres?sslmode=require" \
  -tAc "SELECT 'workers', count(*) FROM workers_worker UNION ALL SELECT 'asignaciones', count(*) FROM scheduling_scheduleassignment UNION ALL SELECT 'usuarios', count(*) FROM users_user;"
```

**Criterios para continuar:** dump terminado sin errores, archivo presente
(`ls -lh backups/supabase_pre_cutover.dump`) y disco con espacio. En caso
contrario, detenerse y resolver antes de seguir.

---

## 6) Fase 2 — Push a main (CI rojo esperado)

1. Merge de `feature/migrate-from-supabase-to-dockerized-postgres` a main y push.
2. En GitHub Actions: el job de **deploy quedará en rojo** (esperado y seguro):
   `up -d` falla por `DB_PASSWORD` ausente antes de tocar contenedores.
3. **Verificar que producción sigue viva** (el sitio responde con normalidad).
4. El objetivo de este push es solo dejar el compose nuevo en el servidor.

> No actualizar aún el secreto `DEPLOY_ENV_FILE`.

---

## 7) Fase 3 — Preparar BD dockerizada y restaurar (servidor, después de Fase 2)

```bash
cd /home/ubuntu/schedules

# 3a. Crear el contenedor db (credenciales inline, SIN tocar .env todavía)
DB_NAME=pariwana_buk DB_USER=pariwana DB_PASSWORD=<NUEVA-CLAVE> \
  docker compose -f docker-compose.prod.yml up -d db

# 3b. Restore (pg_restore 16.13 del contenedor, mismo formato del dump)
docker exec -i pariwana_scheduler_db pg_restore -U pariwana -d pariwana_buk \
  --no-owner --no-privileges -n public \
  < /home/ubuntu/schedules/backups/supabase_pre_cutover.dump

# 3c. Validar conteos restaurados (comparar con la referencia de la Fase 1)
docker exec -i pariwana_scheduler_db psql -U pariwana -d pariwana_buk \
  -c "SELECT (SELECT count(*) FROM tenants_tenant) tenants, (SELECT count(*) FROM tenants_property) sedes, (SELECT count(*) FROM workers_area) areas, (SELECT count(*) FROM workers_worker) workers, (SELECT count(*) FROM scheduling_scheduleassignment) asignaciones, (SELECT count(*) FROM users_user) usuarios;"
```

**Errores esperados en 3b (inofensivos):** roles `authenticated`/`anon`/
`service_role` no existen, schema `auth`/`storage`/`realtime` no existen,
`transaction_timeout` no reconocido (PG17). Ninguno es error de datos.

**Criterio para continuar:** los conteos de 3c coinciden con la referencia.
En caso contrario, detenerse y depurar (no seguir al switch).

---

## 8) Fase 4 — Switch (GitHub, cuando la Fase 3 esté validada)

### 8a. Actualizar el secreto `DEPLOY_ENV_FILE`

En `Settings → Secrets and variables → Actions → DEPLOY_ENV_FILE`, reemplazar
el contenido completo por:

```env
SECRET_KEY=<el mismo actual>
DEBUG=False
ENVIRONMENT=production
ALLOWED_HOSTS=<el mismo actual>
CSRF_TRUSTED_ORIGINS=<el mismo actual>
# PostgreSQL dockerizado (servicio "db" del compose). NO usar ?pgbouncer=true
DB_NAME=pariwana_buk
DB_USER=pariwana
DB_PASSWORD=<NUEVA-CLAVE-de-la-Fase-3>
DB_HOST=db
DB_PORT=5432
DATABASE_URL=postgresql://pariwana:<NUEVA-CLAVE-de-la-Fase-3>@db:5432/pariwana_buk
TIME_ZONE=America/Lima
BUK_EXPORT_DEFAULT_FORMAT=xlsx
BUK_DEFAULT_SHEET_NAME=Reporte carga BUK
```

Reglas:
- `DATABASE_URL` y `DB_*` deben apuntar a la MISMA base y password.
- No incluir `DIRECT_URL` ni `?pgbouncer=true`.
- `SECRET_KEY`/`ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` se conservan iguales.

### 8b. Re-deploy

1. GitHub Actions → **Run workflow** (workflow_dispatch).
2. `web` se recrea contra la BD local: el entrypoint corre `migrate` y el
   healthcheck confirma el arranque (job de deploy en verde).

### 8c. Smoke test post-deploy

1. Login con un usuario real de producción.
2. Carga de Asignación sin errores.
3. Control 15 días visible para Admin/Operador.
4. Preview BUK en rango corto.
5. Export CSV/XLSX BUK.

---

## 9) Rollback (si algo falla en Fase 4)

```bash
cd /home/ubuntu/schedules
cp .env.supabase.bak .env
docker compose -f docker-compose.prod.yml -f docker-compose.deploy.yml up -d web
```

- Supabase sigue intacta (solo lectura) → la app vuelve a funcionar contra ella.
- Se pierde lo escrito en la BD dockerizada durante la ventana (sin dual-write);
  la ventana debe ser corta.
- Luego re-ejecutar desde la Fase 3 (restore) o revertir el secreto anterior.

---

## 10) Fase 5 — Post-cutover (cuando todo esté estable, no antes)

1. **Instalar backups** (el CI no copia scripts al servidor):
   ```bash
   scp scripts/backup_db.sh <user>@<server>:/home/ubuntu/schedules/scripts/
   ssh <user>@<server> 'chmod +x /home/ubuntu/schedules/scripts/backup_db.sh'
   ssh <user>@<server> 'crontab -e'
   # línea: 30 3 * * * /home/ubuntu/schedules/scripts/backup_db.sh >> /home/ubuntu/schedules/backups/backup.log 2>&1
   ```
   Retención: diario 14 días, semanal 8 semanas, mensual 6 meses. Probar un
   restore al menos 1 vez al mes.
2. **Rotar la password de la BD de Supabase** (estuvo commiteada en el repo) y
   revocar el acceso si ya no se usa.
3. **Limpiar referencias:** quitar `*.supabase.co` (y `*.netlify.app` si aplica)
   de `ALLOWED_HOSTS` en el `.env` de producción.
4. (Opcional, con aprobación) eliminar las 22 tablas legadas pre-Django del
   schema `public`.

---

## 11) Verificación final (lista de aceptación)

- [ ] Job de deploy final en verde.
- [ ] Conteos locales == conteos de referencia (Fase 1).
- [ ] Login y flujos principales funcionando (Fase 8c).
- [ ] Cron de backup instalado y ejecutando.
- [ ] Password de Supabase rotada.
- [ ] `ALLOWED_HOSTS` sin referencias a Supabase.
- [ ] `.env` no está en el repo (gitignore + `git rm --cached` ya aplicados).
- [ ] `.env.supabase.bak` conservado localmente al menos 30 días.

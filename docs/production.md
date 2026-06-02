# Produccion y operacion

Este documento resume recomendaciones para desplegar y operar Pariwana BUK Scheduler en entorno productivo.

## 1) Arquitectura recomendada
- Sistema operativo: Linux (Ubuntu LTS).
- App server: `gunicorn` sirviendo Django.
- Reverse proxy: `nginx` con TLS.
- Base de datos: PostgreSQL administrado (Supabase o equivalente).
- Almacenamiento de archivos: bucket privado (si se persisten exportaciones/adjuntos).
- Cache/colas (opcional en v1): Redis.

## 2) Variables de entorno
Usar `.env` con secretos fuera del repositorio.

Variables minimas:
- `SECRET_KEY`
- `DEBUG=false`
- `ALLOWED_HOSTS=<dominio>`
- `DATABASE_URL`
- `TIME_ZONE=America/Lima`
- `DEFAULT_FROM_EMAIL`, `EMAIL_*`
- `MEDIA_ROOT`, `STATIC_ROOT`
- `BUK_DEFAULT_SHEET_NAME=Reporte carga BUK`

Reglas:
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
- Frecuencia recomendada:
  - Full DB diario.
  - PITR/WAL si el proveedor lo soporta.
- Retencion:
  - Diario 14 dias.
  - Semanal 8 semanas.
  - Mensual 6 meses.
- Probar restauracion al menos 1 vez por mes.
- Mantener runbook de restore validado por el equipo.

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

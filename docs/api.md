# API inicial disponible

Regla general:
- En endpoints multi-tenant se envia `tenant_id` y, cuando aplica, `property_id`.
- Alternativamente, `super_admin` puede operar con sesion de soporte activa usando `X-Support-Session-Id`.
- La API valida permisos en backend por rol, tenant, sede y modulo activado.

## Auth
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`

`GET /api/auth/me/`:
- Para usuarios normales devuelve datos basicos del usuario.
- Para `super_admin` incluye bloque `support` con:
  - `header_session_id`
  - `current_session`
  - `active_sessions`

## Usuarios y permisos
- `/api/users/`
- `/api/user-tenant-roles/`
- `/api/user-property-permissions/`
- `/api/user-area-permissions/`

## Core
- `/api/tenants/`
- `/api/properties/`
- `POST /api/tenants/{id}/support-access/start/` (solo super admin)
- `POST /api/tenants/{id}/support-access/stop/` (solo super admin)
- `GET /api/tenants/{id}/support-access/sessions/`
- `GET /api/tenants/support-access/active/` (solo super admin)
- `POST /api/tenants/support-access/stop-all/` (solo super admin)
- `/api/modules/` + `POST /api/modules/toggle/`
- `/api/areas/`
- `/api/workers/`
- `/api/shifts/`
- `/api/special-states/`
- `/api/assignments/`
- `GET /api/assignments/control-next-15-days/`
- `POST /api/assignments/bulk-range-state/`
- `POST /api/assignments/bulk-sundays-state/`
- `POST /api/assignments/bulk-week-pattern/`
- `POST /api/assignments/copy-week/`
- `POST /api/assignments/copy-previous-month/`
- `GET /api/assignments/week-pattern-templates/`
- `POST /api/assignments/save-week-pattern-template/`
- `POST /api/assignments/update-week-pattern-template/`
- `POST /api/assignments/delete-week-pattern-template/`
- `POST /api/assignments/apply-week-pattern-template/`

Nota para operaciones masivas:
- `bulk-range-state`, `bulk-sundays-state`, `bulk-week-pattern`, `copy-week`, `copy-previous-month` y `apply-week-pattern-template` aceptan `dry_run=true` para vista previa de impacto (`to_create`, `to_update`, `unchanged`) sin persistir cambios.

## Imports
- `POST /api/imports/excel-preview/`
- `POST /api/imports/workers-preview/`
- `POST /api/imports/{id}/confirm/`
- `POST /api/imports/{id}/cancel/`
- `GET /api/imports/{id}/rows/`

## BUK
- `POST /api/buk/validate/`
- `POST /api/buk/preview/`
- `POST /api/buk/export/` (format: `xlsx` o `csv`)
- `POST /api/buk/compare-template/` (multipart con `reference_file`)
  - opcional: `download_report=true` para descargar evidencia JSON adjunta.
  - respuesta JSON incluye `compare_log_id` para trazabilidad persistida.
- `GET /api/buk/compare-template-logs/` (historial; filtros `is_compatible`, `user`, `compared_from`, `compared_to`, `page`, `page_size`; incluye metadata de paginacion)
- `GET /api/buk/compare-template-logs/{id}/download/` (JSON persistido por log)
- `GET /api/buk/compare-template-logs/export-csv/` (CSV del historial filtrado)

## Cierre de mes / Auditoria
- `POST /api/month-closure/close/`
- `POST /api/month-closure/reopen/`
- `GET /api/audit/`

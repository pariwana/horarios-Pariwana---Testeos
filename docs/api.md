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

## Cierre de mes / Auditoria
- `POST /api/month-closure/close/`
- `POST /api/month-closure/reopen/`
- `GET /api/audit/`

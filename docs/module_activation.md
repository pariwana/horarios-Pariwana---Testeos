# Activacion modular por tenant

Cada funcionalidad se controla con `ModuleActivation`:
- `tenant`
- `module_key`
- `is_enabled`
- `enabled_by`
- `enabled_at`

## Regla de ejecucion
- Si el modulo esta desactivado:
  - no se muestra en menu,
  - no se habilita endpoint,
  - no se permite operacion en backend.

## API de modulos
- `GET /api/modules/`
- `POST /api/modules/toggle/`

`toggle` requiere:
- `module_key`
- `is_enabled`
- y `tenant_id`, salvo cuando hay sesion de soporte activa.

## Comportamiento con sesion de soporte
Con `X-Support-Session-Id` activo:
- `GET /api/modules/` queda limitado al tenant de la sesion.
- `POST /api/modules/toggle/` puede operar sin `tenant_id`.
- Si se envia un `tenant_id` distinto al tenant de la sesion, responde `403`.

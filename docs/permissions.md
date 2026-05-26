# Permisos

## Capas de validacion
1. Rol global o de tenant (`UserTenantRole`)
2. Permiso por sede (`UserPropertyPermission`)
3. Permiso por area (`UserAreaPermission`)
4. Modulo activado (`ModuleActivation`)

## Roles
- `super_admin`: alcance global.
- `admin`: alcance total dentro del tenant.
- `operator`: operacion en sedes permitidas.
- `supervisor`: vista y asignacion restringida por sede/area.

## Modo soporte (super admin)
El modo soporte usa un contexto activo de tenant/sede mediante el header:

- `X-Support-Session-Id: <session_id>`

Reglas:
- Solo `super_admin` puede usar sesiones de soporte.
- La sesion debe estar activa (`ended_at` nulo).
- La sesion solo puede ser usada por el usuario que la inicio.
- Si hay sesion activa, la API fuerza el alcance al `tenant` de la sesion.
- Si la sesion tiene `property`, la API tambien fuerza esa sede.
- Si el request intenta usar otro `tenant_id` o `property_id`, la API responde `403`.

Efecto operativo:
- Con sesion activa, no siempre es obligatorio enviar `tenant_id`.
- Si un endpoint exige sede, se puede resolver desde la sesion o por `property_id` dentro de alcance.

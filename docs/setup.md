# Setup local

## Requisitos
- Python 3.12+
- PostgreSQL 15+

## Backend
1. Crear entorno virtual.
2. Instalar dependencias:
   - `pip install -r backend/requirements.txt`
3. Crear `backend/.env` a partir de [backend/.env.example](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/backend/.env.example>).
4. Ejecutar migraciones:
   - `python manage.py migrate`
5. Crear super admin inicial:
   - `python manage.py create_initial_super_admin --email admin@pariwana.com --password <password>`
6. Sembrar tenant/sedes iniciales:
   - `python manage.py seed_initial_pariwana`
7. Levantar servidor:
   - `python manage.py runserver`

## Frontend
Decision inicial aprobada para v1: `Django templates + HTMX`.
Se mantiene opcion de desacoplar frontend a React mas adelante.

## Modo soporte (super admin)

### Header
Todas las operaciones de soporte usan:

- `X-Support-Session-Id: <session_id>`

### Flujo sugerido
1. Iniciar sesion normal con super admin.
2. Crear sesion de soporte sobre tenant/sede:
   - `POST /api/tenants/{tenant_id}/support-access/start/`
3. Usar el `id` retornado como `X-Support-Session-Id` en requests posteriores.
4. Consultar sesion activa:
   - `GET /api/tenants/support-access/active/`
5. Cerrar sesion puntual:
   - `POST /api/tenants/{tenant_id}/support-access/stop/`
6. Cerrar todas las sesiones activas del usuario:
   - `POST /api/tenants/support-access/stop-all/`

### Ejemplos de request

Crear sesion de soporte:

```http
POST /api/tenants/1/support-access/start/
Content-Type: application/json

{
  "property_id": 2,
  "reason": "soporte validacion BUK"
}
```

Usar sesion de soporte para listar trabajadores sin `tenant_id`:

```http
GET /api/workers/
X-Support-Session-Id: 15
```

Cerrar todas mis sesiones activas:

```http
POST /api/tenants/support-access/stop-all/
Content-Type: application/json

{
  "reason": "fin de soporte"
}
```

### Reglas clave
- Solo `super_admin` puede usar sesiones de soporte.
- La sesion debe estar activa.
- La sesion solo la puede usar quien la inicio.
- Con sesion activa, el alcance queda limitado al tenant/sede de esa sesion.
- Si el request intenta salir del alcance, la API responde `403`.

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
7. (Opcional recomendado para pruebas UI) Sembrar data demo operativa en Cusco:
   - `python manage.py seed_demo_cusco_data --days 15`
   - Crea/actualiza: areas, turnos, estados especiales, trabajadores y asignaciones en rango.
8. (Opcional recomendado para QA por rol) Crear usuarios demo:
   - `python manage.py seed_demo_users --password StrongPass123`
   - Crea/actualiza:
     - `admin.demo@pariwana.local` (Administrador)
     - `operador.demo@pariwana.local` (Operador)
     - `supervisor.demo@pariwana.local` (Supervisor)
   - El supervisor queda acotado por defecto a `Recepcion` y `Housekeeping`.
9. Levantar servidor:
   - `python manage.py runserver`

## Atajo local en Windows (puerto 8000)
- Desde `backend/`, ejecutar:
  - `run_local_8000.bat`
- Este script aplica migraciones y luego levanta `127.0.0.1:8000`.
- Para revision funcional completa, usar:
  - `bootstrap_and_run_8000.bat`
- Este script prepara demo local, ejecuta preflight de seguridad, QA local, readiness report y luego levanta `127.0.0.1:8000`.

## Bootstrap local rapido (1 comando)
Si quieres preparar todo para pruebas funcionales (tenant/sedes + data Cusco + usuarios demo):

- `python manage.py bootstrap_local_demo --password StrongPass123 --days 15`
- O ejecutar directamente:
  - `bootstrap_and_run_8000.bat`

## Validacion automatica de setup demo
- Verificar que RBAC + modulos + data minima esten correctos:
  - `python manage.py validate_demo_setup`
- Smoke test funcional rapido de WebUI por rol:
  - `python manage.py smoke_test_webui`
- QA local combinado (recomendado):
  - `python manage.py qa_check_local`
- Preflight de seguridad antes de subir a GitHub o desplegar:
  - `python manage.py security_preflight`
- Readiness Fase 4 con bootstrap + QA local:
  - `python manage.py phase4_readiness_report --bootstrap-demo-password StrongPass123 --run-local-qa`

## Guia de prueba por rol
- [qa_role_walkthrough.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/qa_role_walkthrough.md>)

## Frontend
Decision inicial aprobada para v1: `Django templates + HTMX`.
Se mantiene opcion de desacoplar frontend a React mas adelante.

## QA manual recomendado
- Ejecutar checklist por rol antes de liberar cambios:
  - [qa_manual_checklist.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/qa_manual_checklist.md>)
- Estado funcional de la fase actual:
  - [phase4_status.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_status.md>)
- Guia de revision final Fase 4:
  - [phase4_final_review_guide.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_final_review_guide.md>)
- Guia de despliegue/operacion productiva:
  - [production.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/production.md>)

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

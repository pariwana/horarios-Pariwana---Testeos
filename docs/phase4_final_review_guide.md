# Fase 4 - Guia de revision final

## Estado actual
La Fase 4 esta en **90%** por criterio de readiness:
- checks tecnicos principales en verde;
- sin migraciones pendientes;
- WebUI y comandos cubiertos por tests;
- pendiente QA manual por rol;
- pendiente validacion BUK final con archivo operativo real.

## Preparar revision local
Desde [backend](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/backend>):

Opcion recomendada:

```powershell
.\bootstrap_and_run_8000.bat
```

Este script ejecuta:
- migraciones;
- bootstrap demo;
- `security_preflight`;
- `qa_check_local`;
- `phase4_readiness_report`;
- servidor local en `127.0.0.1:8000`.

Opcion manual:

```powershell
$env:PYTHONPATH='C:\Users\frazz\OneDrive\Documentos\App de RRHH Pariwana\backend\.deps'
$env:DATABASE_URL='sqlite:///C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/backend/test.sqlite3'
$env:DEBUG='true'
$env:ALLOWED_HOSTS='127.0.0.1,localhost'
python manage.py bootstrap_local_demo --password StrongPass123 --days 15
python manage.py qa_check_local
python manage.py runserver 127.0.0.1:8000 --noreload
```

Abrir:
- [http://127.0.0.1:8000/app/login/](http://127.0.0.1:8000/app/login/)

## Usuarios demo
- Administrador: `admin.demo@pariwana.local`
- Operador: `operador.demo@pariwana.local`
- Supervisor: `supervisor.demo@pariwana.local`
- Password demo: `StrongPass123`

## Orden recomendado de prueba
1. Login y selector tenant/sede.
2. Dashboard y menu por rol.
3. Trabajadores: crear, editar, desactivar.
4. Areas: crear, editar, desactivar con reasignacion.
5. Turnos: crear, editar, desactivar.
6. Asignacion: editar celda, limpiar celda, acciones masivas, responsive.
7. Control 15 dias: revisar tarjetas por area y corregir desde enlace.
8. Importaciones: trabajadores y turnos por area desde CSV/XLSX.
9. Reporte BUK: preview, validador, XLSX, CSV y comparador.
10. Cierre de mes: cerrar, validar bloqueo, reabrir.
11. Auditoria: verificar acciones registradas.
12. Super Admin: tenants, sedes, modulos, soporte y auditoria global.

## Criterio para marcar 100%
La Fase 4 solo se marca al 100% si:
- no hay errores bloqueantes en la revision visual;
- el flujo de Asignacion es usable en desktop y telefono;
- Control 15 dias permite detectar areas sin horario completo;
- Reporte BUK genera XLSX compatible con la referencia real;
- permisos por rol, sede y area funcionan como se espera;
- cierre/reapertura de mes bloquea y desbloquea correctamente.

Cuando estos puntos esten aprobados, ejecutar:

```powershell
python manage.py phase4_readiness_report --bootstrap-demo-password StrongPass123 --run-local-qa --manual-qa-approved --buk-final-approved --output-file docs/phase4_readiness_report_final.md
```

El reporte debe indicar:
- `Estado: READY_FOR_SIGNOFF`
- `Avance estimado: 100%`

## Resultado esperado hoy
Antes de la revision manual, el reporte correcto es:
- `Estado: TECHNICALLY_READY_PENDING_BUSINESS_QA`
- `Avance estimado: 90%`

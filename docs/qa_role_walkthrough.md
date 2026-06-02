# QA por rol (Demo local)

## Preparar entorno
1. Ir a [backend](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/backend>).
2. Levantar servidor local con demo:
   - `bootstrap_and_run_8000.bat`
3. Validar setup tecnico:
   - `python manage.py qa_check_local`
4. Generar archivos de muestra para probar Importaciones:
   - `python manage.py generate_phase4_import_samples`
   - salida por defecto: `docs/qa_import_samples/`
5. Abrir login:
   - [http://127.0.0.1:8000/app/login/](http://127.0.0.1:8000/app/login/)

## Usuarios demo
- Password comun: `StrongPass123`
- Administrador: `admin.demo@pariwana.local`
- Operador: `operador.demo@pariwana.local`
- Supervisor: `supervisor.demo@pariwana.local`

## Flujo rapido - Administrador (10-15 min)
1. `Asignacion`: editar celdas + acciones masivas + guardar.
2. `Importaciones`: plantilla + preview + confirmar (trabajadores y turnos por area).
3. `Reporte BUK`: preview, validar, exportar CSV/XLSX, probar `exportar con observaciones`.
4. `Cierre de mes`: cerrar, validar bloqueo en Asignacion, reabrir.
5. `Usuarios y permisos`: revisar permisos por sede/area.

Criterio:
- Sin errores 500.
- Puede ejecutar override de exportacion con observaciones.

## Flujo rapido - Operador (8-12 min)
1. `Asignacion`: editar horario en sedes/areas permitidas.
2. `Control 15 dias`: abrir pendiente y corregir desde enlace.
3. `Importaciones`: preview/confirm de turnos por area.
4. `Reporte BUK`: exportar normal.

Criterio:
- No puede usar `exportar con observaciones`.
- No puede operar fuera de su alcance.

## Flujo rapido - Supervisor (6-10 min)
1. `Asignacion`: confirmar visibilidad limitada por area.
2. `Reporte BUK`: verificar que solo vea sus areas.
3. Probar restricciones en modulos de gestion.

Criterio:
- Solo asigna/consulta dentro de permisos.
- Bloqueo correcto en gestion no autorizada.

## Registro de resultado
Completar checklist formal en:
- [qa_manual_checklist.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/qa_manual_checklist.md>)
- [phase4_signoff.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_signoff.md>)

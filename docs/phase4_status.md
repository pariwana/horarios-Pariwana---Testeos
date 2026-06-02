# Estado Fase 4

## Estado actual
Fase 4 en cierre funcional de negocio. Cierre tecnico completado con tests y QA local en verde.

## Implementado en Fase 4
- Cierre/reapertura de mes por sede.
- Bloqueo de edicion en Asignacion cuando el mes esta cerrado.
- Auditoria extendida en acciones criticas.
- Acciones masivas y plantillas de asignacion.
- UX de Asignacion mejorado (filtros en grilla responsive, panel de acciones avanzadas colapsado por defecto, grilla mas legible).
- UX de Asignacion: limpieza de celda con `--` + resaltado visual de celda editada al guardar/eliminar.
- Continuidad de contexto en Asignacion (`worker_q`, `focus_date`).
- Control 15 dias integrado con enlace de correccion a Asignacion.
- Importacion masiva de turnos por area (CSV/XLSX) con preview/confirm.
- Cobertura automatizada agregada para importacion de turnos por area en XLSX (servicio + flujo web).
- Vista de Importaciones ordenada para payloads/resumenes estructurados (sin bloque de texto crudo).
- Hardening de permisos por area para `Supervisor` y `Operador` restringido.
- Validacion automatizada de permisos: operador sin `can_manage_shifts` no puede previsualizar importacion de turnos.
- Comando de seed demo para pruebas funcionales locales en Cusco: `python manage.py seed_demo_cusco_data`.
- Comando de bootstrap local integral para QA: `python manage.py bootstrap_local_demo --password <...> --days 15`.
- Comando de validacion automatica del setup demo (RBAC + modulos + data minima): `python manage.py validate_demo_setup`.
- Smoke test automatizado WebUI por rol: `python manage.py smoke_test_webui`.
- Comando QA local combinado: `python manage.py qa_check_local` (setup validation + smoke webui).
- Comando de preflight de seguridad: `python manage.py security_preflight` para detectar tokens accidentales antes de GitHub/despliegue.
- Comando de readiness Fase 4: `python manage.py phase4_readiness_report` para consolidar bootstrap demo, seguridad, checks automaticos, aprobaciones manuales y porcentaje de cierre.
- Script de revision local validada: `backend/bootstrap_and_run_8000.bat` ejecuta migraciones, bootstrap demo, seguridad, QA local, readiness report y levanta `127.0.0.1:8000`.
- Reporte BUK restringido al alcance de areas autorizadas.
- Indicador en Cierre de mes sobre reporte BUK generado para el periodo.
- Hardening de comparador BUK para normalizar etiquetas con problemas de codificacion (mojibake) en referencia/candidato.
- Ajuste de fidelidad de encabezado BUK: columna fija de area estandarizada a `Área` en la salida.
- Comando para QA manual: generacion automatica de archivos de muestra de importaciones (CSV/XLSX de trabajadores y turnos por area).
- UI de Importaciones con descarga directa de muestras QA (CSV/XLSX) para trabajadores y turnos por area.
- Gestion de Areas desde WebUI: crear, editar, desactivar y reasignar trabajadores/turnos de forma transaccional.
- Gestion de Tenants desde WebUI para Super Administrador: crear, editar, activar/desactivar, settings JSON y auditoria.
- Gestion de Modulos desde WebUI para Super Administrador: activar/desactivar modulos por tenant con auditoria y vista responsive.
- Gestion de Soporte desde WebUI para Super Administrador: iniciar soporte por tenant/sede, activar contexto, cerrar sesiones y auditar inicio/cierre.
- Auditoria global desde WebUI para Super Administrador: filtros por tenant, sede, accion, entidad, usuario y fechas.
- Dashboard global para Super Administrador: estado general de tenants, sedes, trabajadores, modulos deshabilitados, soporte activo, auditoria reciente y cierres recientes.
- Trabajadores y turnos con edicion y baja logica desde WebUI, ocultando inactivos por defecto.
- Usuarios y permisos con desactivacion de cuentas.
- Control 15 dias con resumen por area: trabajadores afectados y dias sin asignacion.
- Control 15 dias con tarjetas visuales por area: nivel de alerta, porcentaje de cobertura, dias requeridos/cubiertos y detalle movil de pendientes.
- Roles configurables por tenant mediante perfiles de rol clonables/customizables y permisos por sede ampliados.
- Administradores limitados a sedes asignadas; Super Administrador conserva alcance global.
- Creacion de sedes con permiso inicial automatico para el administrador creador y auditoria de creacion/edicion.
- Menu WebUI dinamico segun modulo activo y permisos por sede.
- Reporte BUK separado en permiso de vista (`can_view_reports`) y permiso de exportacion (`can_export_buk`).
- Control 15 dias gobernado por permiso especifico `can_use_control`.
- Importaciones y descargas de plantillas/muestras gobernadas por permisos operativos, no por rol rigido.
- Seeds y smoke tests actualizados para los permisos ampliados.
- Asignacion con vista responsive por trabajador para pantallas moviles, encabezados de dia mas claros y contadores operativos de programadas, pendientes y nocturnas.
- Layout base responsive: menu superior desplazable en telefono, formularios a ancho completo y tablas preparadas para scroll horizontal en pantallas pequenas.

## Pendientes para cierre total
1. QA manual final por rol (usar [phase4_final_review_guide.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_final_review_guide.md>) y [qa_manual_checklist.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/qa_manual_checklist.md>)).
2. Ajustes UX menores que surjan de la validacion manual (priorizar Asignacion y Reporte BUK).
3. Validacion final de compatibilidad BUK con archivo de operacion real del equipo.

## Evidencia reciente
- QA local ejecutado el 2026-05-28 con resultado OK:
  - [phase4_qa_run_2026-05-28.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_qa_run_2026-05-28.md>)
- QA local ejecutado el 2026-05-29 con resultado OK (suite completa):
  - [phase4_qa_run_2026-05-29.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_qa_run_2026-05-29.md>)
- Documento de produccion consolidado:
  - [production.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/production.md>)
- Comparacion automatizada contra Excel base (2026-05-28): compatible (`is_compatible=true`, `errors=0`, `warnings=0`)
  - [buk_compare_latest.json](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/buk_compare_latest.json>)
- Acta de cierre funcional para aprobacion de negocio:
  - [phase4_signoff.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_signoff.md>)
- Snapshot integrado de aceptacion (QA local + comparacion BUK) ejecutado el 2026-05-29:
  - [phase4_acceptance_snapshot_2026-05-29.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_acceptance_snapshot_2026-05-29.md>)
- Snapshot de aceptacion contra Excel base ejecutado el 2026-06-02: `check_buk_template_compatibility` PASS, `errors=0`, `warnings=0`:
  - [phase4_acceptance_snapshot_2026-06-02_current.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_acceptance_snapshot_2026-06-02_current.md>)
- Suite WebUI ejecutada el 2026-06-01: `python manage.py test apps.webui.tests` con 139 tests OK.
- Verificacion de migraciones ejecutada el 2026-06-01: `python manage.py makemigrations --check` sin cambios pendientes.
- Suite WebUI reejecutada el 2026-06-01 tras ajuste responsive global: `python manage.py test apps.webui.tests` con 139 tests OK.
- Suite WebUI reejecutada el 2026-06-01 tras mejora visual de Control 15 dias: `python manage.py test apps.webui.tests` con 139 tests OK.
- Suite WebUI reejecutada el 2026-06-01 tras hardening de sedes/permisos: `python manage.py test apps.webui.tests` con 139 tests OK.
- Suite WebUI reejecutada el 2026-06-01 tras gestion WebUI de tenants: `python manage.py test apps.webui.tests` con 143 tests OK.
- Suite WebUI reejecutada el 2026-06-02 tras gestion WebUI de modulos: `python manage.py test apps.webui.tests` con 146 tests OK.
- Suite WebUI reejecutada el 2026-06-02 tras gestion WebUI de soporte: `python manage.py test apps.webui.tests` con 150 tests OK.
- Suite WebUI reejecutada el 2026-06-02 tras auditoria global WebUI: `python manage.py test apps.webui.tests` con 153 tests OK.
- Suite WebUI reejecutada el 2026-06-02 tras dashboard global de Super Administrador: `python manage.py test apps.webui.tests` con 155 tests OK.
- Readiness report generado el 2026-06-02:
  - [phase4_readiness_report_2026-06-02.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_readiness_report_2026-06-02.md>)
- Readiness report con bootstrap demo + seguridad + QA local ejecutado el 2026-06-02: `bootstrap_local_demo` PASS, `makemigrations --check` PASS, `security_preflight` PASS y `qa_check_local` PASS; pendiente QA manual y BUK real:
  - [phase4_readiness_report_2026-06-02_with_qa.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_readiness_report_2026-06-02_with_qa.md>)
- Readiness latest generado el 2026-06-02 para revision local validada:
  - [phase4_readiness_report_latest.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_readiness_report_latest.md>)
- Guia de revision final Fase 4:
  - [phase4_final_review_guide.md](</C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/docs/phase4_final_review_guide.md>)
- Suite ampliada WebUI + comandos ejecutada el 2026-06-02: `python manage.py test apps.webui.tests apps.webui.test_management_commands` con 159 tests OK.
- Suite ampliada WebUI + comandos reejecutada el 2026-06-02 tras mejora de readiness: `python manage.py test apps.webui.tests apps.webui.test_management_commands` con 159 tests OK.
- Suite ampliada WebUI + comandos reejecutada el 2026-06-02 tras preflight de seguridad: `python manage.py test apps.webui.tests apps.webui.test_management_commands` con 161 tests OK.

## Criterio de cierre Fase 4
- Checklist manual aprobado por negocio.
- Sin errores bloqueantes en flujos: Asignacion, Control 15 dias, Reporte BUK, Cierre de mes.
- Permisos por rol/sede/area validados.
- Exportacion BUK validada en escenario real de uso.

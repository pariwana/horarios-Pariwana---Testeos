# AGENTS.md

## Proyecto

Pariwana Scheduler es una aplicación interna para gestionar trabajadores, áreas,
turnos, estados especiales, asignaciones de horarios y exportaciones BUK.

Estado y contexto:

- Tenant inicial: Pariwana Hostels.
- Sedes: Lima y Cusco.
- Estado: producción y estabilización.
- Usuarios: administración, operadores y supervisores.

Prioridades: no romper producción, mantener permisos e integridad tenant–sede–área,
asegurar la exactitud BUK, priorizar UX mobile y hacer cambios pequeños, simples
y verificables.

## Stack real

- Python y Django 5.
- Django REST Framework.
- PostgreSQL.
- Django Templates, JavaScript y CSS.
- OpenPyXL y ReportLab.
- Docker, Docker Compose, Gunicorn y WhiteNoise.
- GitHub Actions, GHCR y servidor Linux.

No existe frontend Node, React, Vite ni uso comprobado de HTMX. No ejecutar comandos
npm salvo que el stack cambie mediante una tarea aprobada.

## Arquitectura

Apps principales: `tenants`, `users`, `workers`, `scheduling`, `buk_exports`,
`imports`, `audit`, `month_closure`, `modules` y `webui`.

- Mantener separación funcional por apps.
- Colocar la lógica de negocio en servicios reutilizables.
- Evitar agregar lógica a `webui/views.py` cuando corresponda a una app o servicio.
- No hacer refactors generales ni cambiar arquitectura sin explicar impacto y
  recibir aprobación.

## Componentes protegidos

No modificar sin alcance y aprobación explícitos:

- Formato, preview, validador y configuración BUK.
- `scheduling` y acciones masivas.
- Importadores.
- Backup y restauración.
- Auditoría.
- Cierre mensual.
- Migraciones existentes.
- Configuración, datos y despliegues de producción.

Todo cambio BUK requiere pruebas de regresión y validación obligatoria antes de
exportar. No afirmar aceptación real de BUK sin comparar con el Excel original o
realizar una carga controlada aprobada.

## Permisos e integridad

Toda autorización debe validarse en backend por usuario, tenant, sede, área y
acción. WebUI y API deben compartir la misma política.

- Ocultar botones o menús no constituye autorización.
- No confiar en IDs ni filtros enviados por el cliente.
- Filtrar los objetos dentro del alcance autorizado antes de leerlos o modificarlos.
- Validar el estado resultante al cambiar tenant, sede o área.
- Mantener coherencia entre tenant–sede, sede–área, área–trabajador,
  trabajador–asignación, rol–tenant y permisos de sede–área.
- No permitir que administradores de tenant modifiquen `is_super_admin` o `is_staff`.
- No administrar usuarios con búsquedas globales sin validar tenant.
- Toda corrección de permisos requiere tests adversariales, incluidos manipulación
  de IDs, acceso directo por URL y aislamiento entre sedes y áreas.

## Git, producción y seguridad

- `main` representa producción y un push o merge puede activar despliegue automático.
- No trabajar directamente en `main`; crear una rama `codex/nombre-corto` por tarea.
- No hacer push, merge, PR, deploy, force push ni reescritura de historial sin
  aprobación explícita.
- No borrar ramas ni mezclar tareas sin aprobación.
- No modificar workflows, infraestructura o configuración de producción sin aprobación.
- No tocar secretos, credenciales, datos reales ni eliminar datos.

## Forma de trabajo y UX

- Para tareas grandes o críticas, presentar primero un plan breve.
- Diagnosticar antes de corregir cuando la causa no sea evidente.
- Leer solo los archivos necesarios y usar búsquedas puntuales.
- Mantener cambios pequeños; no implementar mejoras adicionales ni tocar archivos
  no relacionados.
- No instalar dependencias nuevas sin justificarlo.
- Todo cambio visual debe revisarse mobile-first y mantener desktop funcional.
- Priorizar formularios apilados, botones táctiles, acciones visibles, mensajes
  claros y ausencia de scroll horizontal incómodo.
- Usar como referencia mobile 360 × 780 px.

## Validaciones y cierre

Ejecutar validaciones proporcionales al riesgo. Antes de comandos, confirmar el
entorno y que no se conecta a producción; no aplicar migraciones ni iniciar Docker
si puede ejecutar migraciones automáticamente sin revisar el riesgo.

Comandos habituales desde `backend`, según aplique:

```bash
python manage.py check
python manage.py test [app_o_test_especifico]
python -m compileall [ruta_o_app]
python manage.py makemigrations --check --dry-run
```

Una tarea está lista cuando los tests relevantes pasan, no hay errores evidentes,
se respetan permisos e integridad, se revisa el flujo principal y mobile cuando
corresponde, y se documenta cualquier limitación.

Entrega breve obligatoria: qué se hizo, por qué, cómo probarlo, riesgos o pendientes
y siguiente paso recomendado.

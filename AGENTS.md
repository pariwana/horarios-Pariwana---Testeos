# AGENTS.md

## Proyecto
Aplicación interna de Pariwana Hostels para gestión de horarios y generación del reporte BUK.

## Objetivo principal
La prioridad absoluta es generar correctamente el archivo XLSX de carga de turnos para BUK usando como referencia la pestaña "Reporte carga BUK" del archivo "PRUEBA HORARIOS GENERALES 2026".

## Stack
Backend:
- Django
- Django REST Framework
- PostgreSQL
- OpenPyXL
- django-environ

Frontend:
- React + Vite o Django templates + HTMX, según decisión aprobada.

## Reglas de trabajo
- No empezar a programar sin plan aprobado.
- No asumir el formato BUK.
- Analizar primero el Excel "PRUEBA HORARIOS GENERALES 2026".
- Usar la pestaña "Reporte carga BUK" como referencia del exportador.
- Priorizar exactitud del XLSX BUK sobre velocidad.
- Mantener arquitectura modular y escalable.
- Respetar multi-tenant.
- Pariwana Hostels es el tenant inicial.
- Pariwana Lima y Pariwana Cusco son sedes.
- Los permisos deben validarse por rol, tenant, sede, área y módulo.
- No hardcodear credenciales.
- Usar .env y .env.example.
- Registrar auditoría en acciones críticas.
- Escribir o actualizar tests para cambios relevantes.
- No eliminar datos sin confirmación explícita.
- No instalar dependencias nuevas sin justificarlo.

## Módulos iniciales
- Tenants
- Sedes
- Usuarios y permisos
- Módulos activables
- Trabajadores
- Áreas
- Turnos
- Estados especiales
- Asignación de horarios
- Control próximos 15 días
- Validador BUK
- Vista previa BUK
- Exportador BUK XLSX
- Importador Excel
- Auditoría
- Cierre de mes

## Comandos backend esperados
- python manage.py makemigrations --check
- python manage.py migrate
- python manage.py test
- python manage.py runserver

## Comandos frontend esperados
- npm install
- npm run dev
- npm run build
- npm test

## Criterio de terminado
Una tarea solo está lista si:
- Los tests relevantes pasan.
- No hay errores de sintaxis.
- El cambio respeta permisos por tenant, sede y área.
- El módulo se puede activar/desactivar si corresponde.
- El XLSX BUK se genera con estructura compatible con "Reporte carga BUK".
- El cambio queda documentado cuando afecta comportamiento.
